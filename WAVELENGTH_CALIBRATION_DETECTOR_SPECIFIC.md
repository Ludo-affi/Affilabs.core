# Wavelength Calibration (Detector-Specific)

**Step 2** of calibration is detector-specific to handle different spectrometer types.

**Date**: October 18, 2025
**Status**: ✅ **IMPLEMENTED**

---

## Overview

Different spectrometers have different wavelength calibration methods:
- **Ocean Optics** (USB4000, Flame, etc.): Factory EEPROM calibration (read-only)
- **Generic detectors**: Would require polynomial fitting using calibration lamp (not yet implemented)
- **Custom detectors**: Manual calibration file loading

---

## Supported Detector Types

### 1. **Ocean Optics Spectrometers** ✅ FULLY IMPLEMENTED

**Supported Models**:
- USB4000 (3648 pixels)
- Flame (2048 pixels)
- USB2000 (2048 pixels)
- HR4000 (3648 pixels)
- QE65000 (1044 pixels)

**Method**: Factory EEPROM calibration

**How it works**:
- Ocean Optics spectrometers have wavelength calibration stored in EEPROM during manufacturing
- Calibration uses 4th-order polynomial coefficients
- Accuracy: ±0.1-0.5 nm (factory-guaranteed)
- **No calibration lamp needed** ✅

**Implementation**:
```python
wave_data, serial_number = self._calibrate_wavelength_ocean_optics()
# Reads from EEPROM via self.usb.read_wavelength() or self.usb.get_wavelengths()
```

**Advantages**:
- ✅ Instant (no calibration procedure)
- ✅ Reliable (factory-calibrated)
- ✅ No external equipment needed
- ✅ High accuracy (±0.1-0.5 nm)

**Expected Log Output**:
```
📊 Reading wavelength calibration (detector-specific)...
   Detector type: USB4000
   Method: Factory EEPROM (Ocean Optics)
   Spectrometer serial number: USB40H09247
   ✅ Read 3648 wavelengths from factory calibration
   Range: 190.5 - 885.3 nm
   Resolution: 0.190 nm/pixel
```

---

### 2. **Generic Spectrometers** 🚧 NOT YET IMPLEMENTED

**Method**: Polynomial fitting using calibration lamp

**How it would work**:
1. Acquire spectrum from calibration lamp (Hg/Ar/Ne)
2. Detect emission line peaks in spectrum
3. Match peaks to known wavelengths
4. Fit 3rd-5th order polynomial: `wavelength = f(pixel)`
5. Apply polynomial to all pixels

**Required Equipment**:
- Calibration lamp (Hg, Ar, or Ne)
- Fiber optic coupling to spectrometer

**Current Behavior**:
```
⚠️  Generic detector detected - polynomial calibration not yet implemented
    Attempting to read wavelengths as if Ocean Optics compatible...
```

Falls back to Ocean Optics EEPROM method.

**Accuracy (when implemented)**: ±0.5-2.0 nm (depends on lamp and fitting quality)

**Status**: 🚧 **Placeholder exists, full implementation pending**

**Known Emission Lines (Pre-defined)**:
- **Mercury (Hg)**: 11 strong lines from 253-579 nm
- **Argon (Ar)**: 15 strong lines from 696-912 nm
- **Neon (Ne)**: 25+ lines from 585-754 nm

---

### 3. **Custom Detectors** ✅ FULLY IMPLEMENTED

**Method**: Load pre-computed wavelength array from file

**How it works**:
- Load wavelength calibration from CSV or NPY file
- File must contain one wavelength per pixel
- Units: nanometers (nm)

**File Locations** (checked in order):
1. `calibration/wavelength_calibration.npy` (preferred)
2. `calibration/wavelength_calibration.csv` (fallback)

**File Format Examples**:

**NPY format (preferred)**:
```python
import numpy as np
wavelengths = np.array([190.5, 190.7, 190.9, ...])  # 3648 values
np.save("calibration/wavelength_calibration.npy", wavelengths)
```

**CSV format (alternative)**:
```csv
190.5
190.7
190.9
...
```

**Use Cases**:
- Custom-built spectrometers
- Detectors with external calibration data
- Backup when EEPROM fails
- Research instruments with manual calibration

**Expected Log Output**:
```
📊 Reading wavelength calibration (detector-specific)...
   Detector type: Custom
   Method: Loading from calibration file
   Loading from: calibration\wavelength_calibration.npy
   ✅ Loaded 3648 wavelengths from .npy file
   Range: 200.0 - 1000.0 nm
```

---

## Detector Auto-Detection

The system automatically detects detector type using multiple strategies:

### Detection Strategy (in order):

1. **USB Device Model Name**:
   ```python
   device_info = self.usb.get_device_info()
   model = device_info.get('model')  # "USB4000", "Flame", etc.
   ```

2. **Serial Number Prefix**:
   ```python
   serial = device_info.get('serial_number')
   if serial.startswith("USB4"): return "USB4000"
   if serial.startswith("FLMS"): return "Flame"
   if serial.startswith("HR4"):  return "HR4000"
   ```

3. **Pixel Count Inference**:
   ```python
   pixel_count = len(test_wavelengths)
   if pixel_count == 3648: return "USB4000"
   if pixel_count == 2048: return "Flame"
   if pixel_count == 1044: return "QE65000"
   ```

4. **Default Fallback**:
   ```python
   return "Ocean Optics"  # Safe default
   ```

**Detection Log Output**:
```
   Detected model from USB: USB4000
   OR
   Serial USB40H09247 → USB4000
   OR
   Pixel count 3648 → likely USB4000
   OR
   Could not detect spectrometer model, assuming Ocean Optics compatible
```

---

## Architecture

### Code Structure

**File**: `utils/spr_calibrator.py`

**Methods**:

1. **`_detect_spectrometer_type()`** (Lines 1208-1267):
   - Auto-detects spectrometer type
   - Returns: "USB4000", "Flame", "Generic", "Custom", etc.

2. **`_calibrate_wavelength_ocean_optics()`** (Lines 1269-1321):
   - Reads from Ocean Optics EEPROM
   - Returns: (wavelength_array, serial_number)

3. **`_calibrate_wavelength_from_file()`** (Lines 1323-1368):
   - Loads from external calibration file
   - Returns: (wavelength_array, "custom")

4. **`calibrate_wavelength_range()`** (Lines 1370+):
   - Main method - routes to appropriate sub-method
   - Applies SPR spectral filtering (580-720nm)
   - Calculates Fourier transform weights
   - Saves wavelength data to disk

### Flow Diagram

```
calibrate_wavelength_range()
    │
    ├─> _detect_spectrometer_type()
    │        ├─> Check USB model name
    │        ├─> Check serial number
    │        ├─> Check pixel count
    │        └─> Return detector type
    │
    ├─> Route based on detector type:
    │    │
    │    ├─> "USB4000", "Flame", etc.
    │    │    └─> _calibrate_wavelength_ocean_optics()
    │    │         └─> Read from EEPROM
    │    │
    │    ├─> "Generic"
    │    │    └─> (Not implemented, falls back to Ocean Optics)
    │    │
    │    └─> "Custom"
    │         └─> _calibrate_wavelength_from_file()
    │              └─> Load from calibration/*.npy or *.csv
    │
    └─> Apply SPR filtering (580-720nm)
         └─> Calculate Fourier weights
              └─> Save to disk
```

---

## Calibration Validation

After wavelength calibration, the system validates:

### ✅ **Wavelength Range Check**

**Full Detector Range**:
```python
logger.info(f"📊 Full detector range: {wave_data[0]:.1f} - {wave_data[-1]:.1f} nm ({len(wave_data)} pixels)")
```

**Expected**:
- UV-VIS: 190-1100 nm (Ocean Optics USB4000, Flame)
- NIR: 900-1700 nm (NIR-optimized detectors)

### ✅ **SPR Spectral Filtering**

**Applied automatically** to focus on SPR-relevant wavelengths:

```python
# Configured in detector profile or settings.py
min_wavelength = 580 nm  # MIN_WAVELENGTH
max_wavelength = 720 nm  # MAX_WAVELENGTH

# Creates mask and filters wavelength array
wavelength_mask = (wave_data >= min_wavelength) & (wave_data <= max_wavelength)
filtered_wave_data = wave_data[wavelength_mask]
```

**Log Output**:
```
✅ SPECTRAL FILTERING APPLIED: 580-720 nm
   Filtered range: 580.3 - 719.8 nm
   Pixels used: 739 (was 3648)
   Resolution: 0.189 nm/pixel
```

### ✅ **Serial-Specific Corrections**

Some detectors require wavelength offset correction:

```python
# Example: Flame FLMT06715 needs +offset
if serial_number == "FLMT06715":
    wave_data = wave_data + WAVELENGTH_OFFSET
```

---

## Storage and Persistence

Wavelength data is saved to disk for:
- Longitudinal data processing
- Post-processing analysis
- Debugging and verification

**Save Locations**:
```python
calib_dir = Path(ROOT_DIR) / "calibration_data"

# Timestamped file
wave_file = calib_dir / f"wavelengths_{timestamp}.npy"
np.save(wave_file, filtered_wave_data)

# Latest (for easy access)
latest_wave = calib_dir / "wavelengths_latest.npy"
np.save(latest_wave, filtered_wave_data)
```

**Format**: NumPy `.npy` (binary, efficient)

**Contents**: Filtered wavelength array (SPR range only, e.g., 580-720nm)

---

## Testing Procedures

### Test 1: Ocean Optics Detector (Standard)

**Expected Result**: Auto-detect and read from EEPROM

```bash
python run_app.py
# Watch for Step 2 logs:
```

**Expected Logs**:
```
📊 Reading wavelength calibration (detector-specific)...
   Detector type: USB4000
   Method: Factory EEPROM (Ocean Optics)
   Spectrometer serial number: USB40H09247
   ✅ Read 3648 wavelengths from factory calibration
   Range: 190.5 - 885.3 nm
   Resolution: 0.190 nm/pixel
📊 Full detector range: 190.5 - 885.3 nm (3648 pixels)
✅ SPECTRAL FILTERING APPLIED: 580-720 nm
   Filtered range: 580.3 - 719.8 nm
   Pixels used: 739 (was 3648)
   Resolution: 0.189 nm/pixel
```

---

### Test 2: Custom Detector (File-Based)

**Setup**: Create calibration file

```python
import numpy as np
from pathlib import Path

# Create calibration directory
Path("calibration").mkdir(exist_ok=True)

# Generate wavelength array (example: linear 200-1000nm over 3648 pixels)
wavelengths = np.linspace(200, 1000, 3648)

# Save as NPY
np.save("calibration/wavelength_calibration.npy", wavelengths)
```

**Run calibration**:
```bash
python run_app.py
```

**Expected Logs**:
```
📊 Reading wavelength calibration (detector-specific)...
   Detector type: Custom
   Method: Loading from calibration file
   Loading from: calibration\wavelength_calibration.npy
   ✅ Loaded 3648 wavelengths from .npy file
   Range: 200.0 - 1000.0 nm
📊 Full detector range: 200.0 - 1000.0 nm (3648 pixels)
✅ SPECTRAL FILTERING APPLIED: 580-720 nm
   Filtered range: 580.1 - 719.9 nm
   Pixels used: 636 (was 3648)
```

---

### Test 3: Verify Detection Logic

**Check what detector was identified**:

```python
# After running calibration, check logs for:
grep "Detector type:" logs/app.log

# Should show one of:
# Detector type: USB4000
# Detector type: Flame
# Detector type: Ocean Optics
# Detector type: Custom
```

---

## Comparison Table

| Detector Type | Method | Accuracy | Equipment | Time | Status |
|---------------|--------|----------|-----------|------|--------|
| **Ocean Optics** | EEPROM | ±0.1-0.5 nm | None | <0.1s | ✅ Implemented |
| **Generic** | Polynomial | ±0.5-2.0 nm | Cal. lamp | ~10-30s | 🚧 Placeholder |
| **Custom** | File-based | Varies | Pre-calibration | <0.1s | ✅ Implemented |

---

## Future Enhancements

### Polynomial Calibration Implementation (Generic Detectors)

**TODO**: Implement full polynomial wavelength calibration

**Required Steps**:
1. ✅ Peak detection using `scipy.signal.find_peaks`
2. ✅ Pattern matching to known emission lines
3. ✅ Outlier rejection (RANSAC or Huber robust fitting)
4. ✅ Cross-validation with reserved peaks
5. ✅ Interactive GUI for manual peak selection (if auto-match fails)

**Placeholder Location**: Could be implemented as:
- `utils/wavelength_calibration.py` - Standalone module
- `WavelengthCalibrator` class with `calibrate()` method

**Known Emission Lines** (already defined for future use):
- **Mercury (Hg)**: 11 strong lines from 253-579 nm
- **Argon (Ar)**: 15 strong lines from 696-912 nm
- **Neon (Ne)**: 25+ lines from 585-754 nm
- **Hg-Ar combo**: Best for broad spectral coverage

**Recommended Polynomial Order**:
- 3rd order: Good for most spectrometers
- 4th order: Ocean Optics standard
- 5th order: High-end gratings with nonlinearity

---

## Error Handling

### Missing Wavelength Data
```
❌ Failed to obtain wavelength calibration
```
**Cause**: EEPROM read failed, no calibration file found
**Solution**: Check USB connection, create calibration file for custom detectors

### No Wavelength Method
```
❌ USB spectrometer has no wavelength reading method
   Expected: read_wavelength() or get_wavelengths()
```
**Cause**: HAL adapter missing wavelength methods
**Solution**: Implement wavelength reading in HAL adapter, or use file-based method

### File Not Found
```
❌ No wavelength calibration file found
   Expected: calibration/wavelength_calibration.csv or calibration/wavelength_calibration.npy
   Please create calibration file or use Ocean Optics detector
```
**Cause**: Custom detector selected but no calibration file exists
**Solution**: Create `calibration/wavelength_calibration.npy` with wavelength array

---

## Summary

✅ **Step 2 is now detector-specific** and supports:
1. **Ocean Optics detectors** - Automatic EEPROM reading (fully implemented)
2. **Custom detectors** - File-based calibration loading (fully implemented)
3. **Generic detectors** - Placeholder for polynomial calibration (future enhancement)

**Key Benefits**:
- ⚡ Instant for Ocean Optics (factory calibration)
- 🔧 Flexible for custom systems (file loading)
- 🚀 Extensible for future detector types (polynomial fitting)

**Current implementation works for all Ocean Optics spectrometers and custom systems with pre-calibrated wavelength files.**
