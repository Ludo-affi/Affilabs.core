# Phase Photonics Modifications - Key Differences Analysis

## Overview
Analysis of `Phase Photonics Modifications` folder to understand what changes they made to operate their detector.

## 🔍 Key Findings

### 1. **SpectrometerAPI Changes**

**File**: `Phase Photonics Modifications/utils/SpectrometerAPI.py`

#### Critical Differences from Original:

**SENSOR_DATA_LEN**:
```python
# Original: SENSOR_DATA_LEN = 3700
# Phase Photonics: SENSOR_DATA_LEN = 1848  # = 3696/2
```
- **Reduced by ~52%** - Phase Photonics detector has fewer pixels
- All array allocations must use 1848 instead of 3700

**Thread Safety (NEW)**:
```python
from threading import Lock

class SpectrometerAPI:
    def __init__(self, dllPathStr: str):
        self.sensor_t_dll = ctypes.CDLL(dllPathStr)
        self.sensor_frame = SENSOR_FRAME_T()  # Pre-allocated frame
        self.lock = Lock()  # NEW: Thread safety
```
- Added `threading.Lock()` for concurrent access
- Pre-allocates `SENSOR_FRAME_T` object for reuse (performance)
- `usb_read_pixels()` uses lock to protect shared frame buffer

**Structure Packing (NEW)**:
```python
class config_contents(ctypes.Structure):
    _pack_ = 1      # NEW: 1-byte alignment
    _layout_ = "ms"  # NEW: Microsoft layout
    _fields_ = [("data", ctypes.c_uint8 * CONFIG_DATA_AREA_SIZE)]

class SENSOR_STATE_T(ctypes.Structure):
    _pack_ = 1      # NEW
    _layout_ = "ms"  # NEW
    _fields_ = [...]
```
- Added proper structure packing for DLL compatibility
- Required for correct memory layout when calling C functions

**New Method - usb_read_pixels()**:
```python
def usb_read_pixels(self, ftHandle, data_type=np.float32):
    """Thread-safe pixel reading with lock protection."""
    self.lock.acquire()
    ret_val = self.usb_read_image_v2(ftHandle, self.sensor_frame)
    pixel_data = np.asarray(self.sensor_frame.pixels, dtype=data_type)
    self.lock.release()
    return (ret_val, pixel_data)
```
- High-performance reading with pre-allocated buffer
- Thread-safe with explicit locking
- Direct numpy conversion with configurable data type

### 2. **USB4000 Wrapper Changes**

**File**: `Phase Photonics Modifications/utils/usb4000.py`

#### Key Differences:

**Device Enumeration**:
```python
from ftd2xx import listDevices

# Uses FTDI device enumeration instead of SeaBreeze
self.devs = [s.decode() for s in listDevices() if s.startswith(b"ST")]
```
- Uses `ftd2xx` library (not SeaBreeze)
- Looks for devices with serial starting with "ST"
- Different USB communication stack entirely

**DLL Selection**:
```python
if self.serial_number == "ST00005":
    self.api = SpectrometerAPI(Path(__file__).parent / "SensorT_x64.dll")
else:
    self.api = SpectrometerAPI(Path(__file__).parent / "Sensor.dll")
```
- Device-specific DLL selection
- "ST00005" gets 64-bit DLL
- Others get 32-bit DLL

**Integration Time Setting**:
```python
def set_integration(self, integration):
    r = self.api.usb_set_interval(self.spec, int(integration * 1000))
    sleep(0.3)  # 300ms delay after setting
    return bool(r)
```
- Integration time in **microseconds** (multiply ms by 1000)
- ⚠️ Originally had 0.3s delay (now removed per user request)

**Modified read_intensity()**:
```python
def read_intensity(self, data_type=np.float64):
    """NEW: Accepts data_type parameter for uint16 support."""
    return self.api.usb_read_pixels(self.spec, data_type)[1]
```
- Added `data_type` parameter (defaults to float64)
- Can return uint16 for raw pixel data
- Returns numpy array directly (not scalar)

### 3. **Main Application Changes**

**File**: `Phase Photonics Modifications/main/main.py`

#### Import Changes:
```python
from utils.SpectrometerAPI import SENSOR_FRAME_T  # NEW: Direct frame access
from utils.usb4000 import USB4000  # Uses Phase Photonics version
```

#### Critical Memory Management Change (Lines 1481-1502)

**OEM Statement**: "We changed the call to read_intensity(..) to sort out memory management."

**Original Approach** (Ocean Optics):
```python
# Multiple calls to read_spectrum() with internal averaging
int_data_sum = np.zeros(...)
for scan in range(num_scans):
    spectrum = self.usb.read_spectrum()  # Returns averaged float64
    int_data_sum += spectrum
```

**Phase Photonics Approach** (Lines 1481-1502):
```python
# Direct uint16 pixel access - no intermediate buffering
int_data_sum = np.zeros_like(self.wave_data, "u4")  # uint32 accumulator
sDT = 0.0  # Frame rate tracking

for _scan in range(self.num_scans):
    t0 = time.time()
    # KEY CHANGE: data_type=np.uint16 for memory efficiency
    pixel_data = self.usb.read_intensity(data_type=np.uint16)
    dt = time.time() - t0
    sDT += dt

    # Direct array slicing - NO framebuffer() conversion needed
    # pixel_data is already uint16 numpy array
    int_data_sum += pixel_data[offset:offset + num]

# TEMPORARY: Auto-closing message with frame rate
show_message(msg_type="Information",
             msg=f"Average frame rate for {self.num_scans} scans: {float(self.num_scans)/sDT}",
             auto_close_time=2)
```

**Key Memory Management Improvements**:
1. **uint16 vs float64**: 50% memory reduction per frame
2. **No intermediate buffering**: Direct pixel access from DLL
3. **uint32 accumulator**: Prevents overflow during summation
4. **Pre-allocated buffer**: Reused in SpectrometerAPI (no repeated allocation)
5. **No framebuffer() conversion**: Phase Photonics returns numpy array directly

**Why This Matters**:
- Ocean Optics path allocates/deallocates float64 arrays repeatedly
- Phase Photonics reuses pre-allocated uint16 buffer in SpectrometerAPI
- For high-speed acquisition (many scans), this dramatically reduces GC pressure
- Memory footprint reduced by ~50% (uint16 vs float64)

#### Frame Rate Monitoring (Lines 1499-1501)

**OEM Statement**: "Towards the end there is a show_message(..) function that shows a pop up message box that auto closes in 2 seconds that shows the average frame rate for the number of scans the client did. This is just temporary, but you can comment this out."

```python
# TEMPORARY: Can be commented out
show_message(msg_type="Information",
             msg=f"Average frame rate for {self.num_scans} scans: {float(self.num_scans)/sDT}",
             auto_close_time=2)
```

**Purpose**:
- Diagnostic tool during development
- Shows actual achieved frame rate
- Auto-closes after 2 seconds
- **Action**: Comment out for production use

### 4. **Integration Limits**

```python
# Phase Photonics (from usb4000.py)
self.min_integration = 0  # No minimum!
self.max_integration = 5_000_000  # 5000 seconds (very high)

# Original software settings (from settings.py)
MIN_INTEGRATION = 0.1  # 0.1ms minimum
MAX_INTEGRATION = 25    # 25ms maximum
```
- Phase Photonics has much wider range
- No enforced minimum (hardware dependent)
- Very high maximum (5000 seconds)

## 🎯 Critical Implementation Points

### Must-Have Changes:

1. **Update SENSOR_DATA_LEN**: `3700 → 1848` in SpectrometerAPI.py
2. **Add Threading**: Import Lock, add to SpectrometerAPI.__init__()
3. **Structure Packing**: Add `_pack_ = 1` and `_layout_ = "ms"` to structures
4. **New Method**: Implement `usb_read_pixels()` with lock protection
5. **Device Enumeration**: Use `ftd2xx.listDevices()` not SeaBreeze
6. **Integration Units**: Microseconds (multiply ms × 1000)
7. **Data Type Support**: Add `data_type` parameter to read_intensity()

### Removed (Per User):
- ❌ **0.3s delay after set_integration()** - User confirmed unnecessary

### Nice-to-Have:
- Pre-allocated SENSOR_FRAME_T for performance
- Device-specific DLL selection logic
- Frame rate monitoring capability

## 📊 Performance Implications

**Phase Photonics Advantages**:
- ✅ Fewer pixels (1848 vs 3700) = faster reads
- ✅ uint16 data type = half memory footprint
- ✅ Pre-allocated buffers = no allocation overhead
- ✅ Thread-safe by design
- ✅ No post-set delay = faster integration changes

**Potential Issues**:
- ⚠️ Lower spectral resolution (fewer pixels)
- ⚠️ Different wavelength range/coverage
- ⚠️ Requires FTDI drivers (ftd2xx)

## 🔧 Implementation Checklist

When implementing PhasePhotonics wrapper:

### SpectrometerAPI.py Updates:
- [ ] Change SENSOR_DATA_LEN to 1848
- [ ] Import threading.Lock
- [ ] Add _pack_ = 1 to all ctypes.Structure classes
- [ ] Add _layout_ = "ms" to all ctypes.Structure classes
- [ ] Add self.lock in __init__()
- [ ] Implement usb_read_pixels() with lock
- [ ] Add pre-allocated sensor_frame buffer

### phase_photonics_wrapper.py Implementation:
- [ ] Import ftd2xx for device enumeration
- [ ] Implement device detection (serial starts with "ST")
- [ ] Add DLL selection logic (Sensor.dll vs SensorT_x64.dll)
- [ ] Implement read_intensity(data_type=np.float64)
- [ ] Return numpy array (not scalar) from read_intensity()
- [ ] Set integration in microseconds (ms × 1000)
- [ ] Remove any post-set delays

### Testing:
- [ ] Verify SENSOR_DATA_LEN = 1848 everywhere
- [ ] Test thread safety under load
- [ ] Verify uint16 data type support
- [ ] Check wavelength calibration (1848 points)
- [ ] Test frame rate performance
- [ ] Validate integration time range

## 📝 Code Examples

### Device Connection:
```python
from ftd2xx import listDevices
from pathlib import Path
from .SpectrometerAPI import SpectrometerAPI

# Find Phase Photonics devices
devs = [s.decode() for s in listDevices() if s.startswith(b"ST")]
serial_number = devs[0]

# Select appropriate DLL
if serial_number == "ST00005":
    dll_path = Path(__file__).parent / "SensorT_x64.dll"
else:
    dll_path = Path(__file__).parent / "Sensor.dll"

# Initialize API with thread safety
api = SpectrometerAPI(str(dll_path))
handle = api.usb_initialize(serial_number)
```

### Setting Integration Time:
```python
# Convert milliseconds to microseconds
integration_us = int(integration_ms * 1000)
result = api.usb_set_interval(handle, integration_us)
# No delay needed!
```

### Reading Spectrum:
```python
# Raw data (uint16)
_, raw_pixels = api.usb_read_pixels(handle, data_type=np.uint16)

# Float data
_, float_pixels = api.usb_read_pixels(handle, data_type=np.float64)

# Result is numpy array of length 1848
assert len(raw_pixels) == 1848
```

### Wavelength Calibration:
```python
from numpy import arange
from numpy.polynomial import Polynomial

# Read calibration from device
bytes_read, config = api.usb_read_config(handle, 0)
coeffs = frombuffer(config.data, ">f8", 4, 3072)
calibration_curve = Polynomial(coeffs)

# Generate wavelength array (1848 points!)
wavelengths = calibration_curve(arange(1848))
```

## ⚠️ Breaking Changes

These changes will break existing USB4000 code if applied globally:

1. **SENSOR_DATA_LEN change** - All array operations affected
2. **read_intensity() signature** - Added data_type parameter
3. **Device enumeration** - Completely different (ftd2xx vs SeaBreeze)
4. **DLL dependency** - Requires SensorT.dll instead of SeaBreeze
5. **Structure packing** - Memory layout changes

**Solution**: Keep Phase Photonics in separate wrapper file (`phase_photonics_wrapper.py`), maintain both detectors independently.

---

**Status**: Analysis complete ✅
**Delay Removed**: Yes (per user request) ✅
**Implementation Ready**: Yes, use this as reference ✅
**Last Updated**: November 19, 2025
