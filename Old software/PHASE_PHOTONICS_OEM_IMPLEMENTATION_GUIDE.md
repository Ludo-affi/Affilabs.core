# Phase Photonics OEM Implementation Guide

## Executive Summary

This document consolidates **all** Phase Photonics implementation guidance, including critical OEM-provided notes about memory management optimization. This is your complete production implementation reference.

---

## 1. Hardware Specifications

| Aspect | Value | Notes |
|--------|-------|-------|
| **Sensor Type** | Phase Photonics Custom | Different from Ocean Optics USB4000 |
| **Pixel Count** | 1848 | vs USB4000: 3700 pixels |
| **Data Type** | uint16 native | Critical for memory efficiency |
| **Interface** | USB via ftd2xx | Not SeaBreeze library |
| **DLL Location** | `Phase Photonics Modifications/utils/` | SensorT_x64.dll / Sensor.dll |
| **Thread Safety** | Required | SpectrometerAPI uses threading.Lock() |

---

## 2. Critical Memory Management Pattern (OEM Guidance)

### 2.1 The Problem

**Original Ocean Optics Approach:**
```python
# Multiple float64 allocations per scan
for scan in range(num_scans):
    spectrum = self.usb.read_spectrum()  # Allocates float64 array
    int_data_sum += spectrum             # More allocations
    # Heavy garbage collection pressure
```

**Issues:**
- Each scan allocates new float64 array
- Conversion overhead from uint16 → float64
- Garbage collection pressure during acquisition
- ~8 bytes per pixel × 1848 pixels = 14.8 KB per scan
- High-speed acquisition (100+ scans) = MB of temporary allocations

### 2.2 Phase Photonics Solution (Lines 1481-1502)

**OEM Statement**: "We changed the call to read_intensity(..) to sort out memory management."

```python
# EFFICIENT: Pre-allocate uint32 accumulator (prevents overflow)
int_data_sum = np.zeros_like(self.wave_data, "u4")  # uint32, reused
sDT = 0.0  # Frame rate tracking

for _scan in range(self.num_scans):
    t0 = time.time()

    # KEY: data_type=np.uint16 returns native detector data
    pixel_data = self.usb.read_intensity(data_type=np.uint16)

    dt = time.time() - t0
    sDT += dt

    # Direct accumulation - NO conversion, NO framebuffer()
    # "pixel data is already uint16_t numpy array..
    #  So framebuffer(..) is not required" - OEM
    int_data_sum += pixel_data[offset:offset + num]

# Average after all scans (single division operation)
averaged_spectrum = int_data_sum / self.num_scans
```

### 2.3 Memory Benefits

| Aspect | Ocean Optics | Phase Photonics | Improvement |
|--------|--------------|-----------------|-------------|
| **Per-pixel size** | 8 bytes (float64) | 2 bytes (uint16) | **75% reduction** |
| **Per-frame memory** | ~14.8 KB | ~3.7 KB | **75% reduction** |
| **Allocations per scan** | 2-3 arrays | 0 (reused buffer) | **Zero allocation** |
| **GC pressure** | High | Minimal | **Dramatic reduction** |
| **Conversion overhead** | uint16→float64 | None | **Direct access** |

### 2.4 Implementation Requirements

1. **Update SpectrometerAPI (wrapper)**:
   ```python
   def read_intensity(self, data_type=None):
       """
       Args:
           data_type: Pass np.uint16 for optimal performance
       Returns:
           numpy array (1848 elements, dtype as specified)
       """
       if data_type is None:
           data_type = np.uint16  # Default to efficient mode

       # Return pre-allocated buffer from SpectrometerAPI
       return self.api.get_frame_data(data_type=data_type)
   ```

2. **Update acquisition code (main.py)**:
   ```python
   # OLD (USB4000):
   spectrum = self.usb.read_spectrum()  # float64

   # NEW (Phase Photonics):
   int_data_sum = np.zeros(1848, dtype=np.uint32)  # Pre-allocate
   for scan in range(num_scans):
       pixel_data = self.usb.read_intensity(data_type=np.uint16)
       int_data_sum += pixel_data[offset:offset+num]
   averaged = int_data_sum / num_scans
   ```

---

## 3. API Changes Summary

### 3.1 SpectrometerAPI.py (NEW)

```python
import threading
import numpy as np
from .Sensor import SensorT  # Native DLL wrapper

class SpectrometerAPI:
    SENSOR_DATA_LEN = 1848  # Fixed pixel count

    def __init__(self):
        self.sensor = SensorT()
        self.lock = threading.Lock()  # Thread safety
        self._frame_buffer = np.zeros(self.SENSOR_DATA_LEN, dtype=np.uint16)

    def set_integration_time(self, time_us: int):
        """Set integration time in MICROSECONDS (not milliseconds)"""
        with self.lock:
            self.sensor.SetIntegrationTime(time_us)

    def read_intensity(self, data_type=None):
        """
        Read frame data into pre-allocated buffer.

        Args:
            data_type: np.uint16 for native data (most efficient)
        Returns:
            numpy array (1848 elements)
        """
        if data_type is None:
            data_type = np.uint16

        with self.lock:
            self.sensor.ReadFrame(self._frame_buffer)  # Reuse buffer
            if data_type == np.uint16:
                return self._frame_buffer  # Direct reference
            else:
                return self._frame_buffer.astype(data_type)  # Convert if needed
```

**Key Features:**
- **Pre-allocated buffer**: `_frame_buffer` reused for every read
- **Thread-safe**: `threading.Lock()` protects concurrent access
- **Zero-copy when possible**: Returns direct buffer reference for uint16
- **Microsecond timing**: Integration time × 1000 vs USB4000

### 3.2 USB4000.py Adapter (MODIFIED)

```python
from .SpectrometerAPI import SpectrometerAPI

class USB4000:
    """Adapter wrapping SpectrometerAPI to match Ocean Optics interface"""

    def __init__(self):
        self.api = SpectrometerAPI()
        self.wavelengths = None  # Load from calibration

    def set_integration_time(self, time_ms: float):
        """Convert milliseconds to microseconds"""
        time_us = int(time_ms * 1000)
        self.api.set_integration_time(time_us)

    def read_intensity(self, data_type=None):
        """Pass-through with optional type conversion"""
        return self.api.read_intensity(data_type=data_type)

    def read_wavelength(self):
        """Return wavelength array (from calibration)"""
        return self.wavelengths

    def read_spectrum(self):
        """Return (wavelengths, intensities) tuple"""
        intensities = self.read_intensity(data_type=np.float64)  # For compatibility
        return (self.wavelengths, intensities)
```

---

## 4. Configuration Changes

### 4.1 config.json

```json
{
  "detector_type": "PhasePhotonics",
  "detector_settings": {
    "integration_time": 10.0,
    "scans_to_average": 5,
    "pixel_count": 1848
  }
}
```

### 4.2 main.py Detector Selection

```python
# Line ~200-217
detector_type = self.config.get('detector_type', 'USB4000')

if detector_type == 'PhasePhotonics':
    from utils.phase_photonics_wrapper import PhasePhotonics
    self.usb = PhasePhotonics()
    logger.info("Using Phase Photonics detector (1848 pixels)")
else:
    from utils.usb4000 import USB4000
    self.usb = USB4000()
    logger.info("Using Ocean Optics USB4000 detector (3700 pixels)")
```

---

## 5. Frame Rate Monitoring (Optional)

**OEM Statement**: "Towards the end there is a show_message(..) function that shows a pop up message box that auto closes in 2 seconds that shows the average frame rate for the number of scans the client did. This is just temporary, but you can comment this out."

```python
# TEMPORARY: Frame rate diagnostic (comment out for production)
show_message(
    msg_type="Information",
    msg=f"Average frame rate for {self.num_scans} scans: {float(self.num_scans)/sDT}",
    auto_close_time=2
)
```

**When to Use:**
- During development/validation
- Troubleshooting performance issues
- Verifying integration time settings

**For Production:**
- Comment out or remove
- Replace with logging if needed:
  ```python
  avg_fps = float(self.num_scans) / sDT
  logger.debug(f"Acquisition frame rate: {avg_fps:.1f} fps")
  ```

---

## 6. Migration Checklist

### Phase 1: Infrastructure
- [ ] Copy `Phase Photonics Modifications/utils/SensorT_x64.dll` to `utils/`
- [ ] Install ftd2xx: `pip install ftd2xx`
- [ ] Create `utils/SpectrometerAPI.py` (thread-safe wrapper)
- [ ] Modify `utils/usb4000.py` to use SpectrometerAPI
- [ ] Update `utils/phase_photonics_wrapper.py` with real implementation

### Phase 2: Integration Time
- [ ] Find all `set_integration_time()` calls
- [ ] Verify millisecond → microsecond conversion (× 1000)
- [ ] Remove 0.3s post-set delay (not needed)

### Phase 3: Memory Management
- [ ] Update all acquisition loops to use `data_type=np.uint16`
- [ ] Pre-allocate uint32 accumulation buffers
- [ ] Remove framebuffer() conversion calls
- [ ] Test with high num_scans (100+) to verify GC reduction

### Phase 4: Configuration
- [ ] Add `detector_type` to config.json
- [ ] Update main.py detector selection logic
- [ ] Handle 1848 vs 3700 pixel differences (ROI, wavelength mapping)

### Phase 5: Testing
- [ ] Verify wavelength calibration (1848 pixels)
- [ ] Test integration time accuracy (microseconds)
- [ ] Validate frame rate (optional show_message)
- [ ] Check memory usage during multi-scan acquisition
- [ ] Thread safety testing (concurrent reads)

---

## 7. Code Examples

### 7.1 Basic Acquisition (Single Scan)

```python
# Initialize
usb = PhasePhotonics()
usb.open()
usb.set_integration_time(10.0)  # 10ms

# Read
wavelengths = usb.read_wavelength()  # (1848,)
intensities = usb.read_intensity(data_type=np.uint16)  # (1848,) uint16

# Use
max_intensity = intensities.max()
print(f"Peak intensity: {max_intensity}")
```

### 7.2 Multi-Scan Averaging (Optimized)

```python
num_scans = 100
offset = 0  # Start of ROI
num = 1848  # Full sensor

# Pre-allocate accumulator (uint32 prevents overflow)
int_data_sum = np.zeros(num, dtype=np.uint32)

# Efficient loop (zero allocations)
for scan in range(num_scans):
    pixel_data = usb.read_intensity(data_type=np.uint16)
    int_data_sum += pixel_data[offset:offset + num]

# Single division at end
averaged_spectrum = int_data_sum / num_scans  # → float64
```

### 7.3 Integration with Existing Code

```python
# OLD (USB4000):
def acquire_spectrum(self):
    spectrum = self.usb.read_spectrum()  # → (wavelengths, intensities)
    return spectrum[1]  # intensities as float64

# NEW (Phase Photonics - memory efficient):
def acquire_spectrum(self):
    if self.config.get('detector_type') == 'PhasePhotonics':
        # Efficient uint16 accumulation
        int_sum = np.zeros(1848, dtype=np.uint32)
        for _ in range(self.num_scans):
            int_sum += self.usb.read_intensity(data_type=np.uint16)
        return int_sum / self.num_scans  # → float64
    else:
        # Ocean Optics path (unchanged)
        spectrum = self.usb.read_spectrum()
        return spectrum[1]
```

---

## 8. Performance Expectations

### 8.1 Memory Usage

| Scenario | USB4000 | Phase Photonics | Savings |
|----------|---------|-----------------|---------|
| **1 scan** | ~15 KB | ~4 KB | 73% |
| **10 scans** | ~150 KB | ~4 KB | 97% |
| **100 scans** | ~1.5 MB | ~4 KB | 99.7% |

### 8.2 Frame Rate

Expected frame rates with Phase Photonics:
- **1 ms integration**: ~800-900 fps
- **10 ms integration**: ~95-99 fps
- **100 ms integration**: ~9.9 fps

*(Actual rates depend on USB bus, CPU, system load)*

---

## 9. Troubleshooting

### Issue: "DLL not found"
**Solution**: Copy SensorT_x64.dll to `utils/` or system PATH

### Issue: Frame rate lower than expected
**Solution**:
1. Enable frame rate message (lines 1499-1501)
2. Check integration time setting (microseconds!)
3. Verify USB connection (ftd2xx device list)

### Issue: Memory still high
**Solution**:
1. Verify `data_type=np.uint16` in all read_intensity() calls
2. Check accumulation uses uint32, not float64
3. Ensure SpectrometerAPI reuses _frame_buffer

### Issue: Thread safety errors
**Solution**: Verify SpectrometerAPI.lock is used around all sensor calls

---

## 10. Key Differences Summary

| Aspect | USB4000 (Ocean Optics) | PhasePhotonics |
|--------|------------------------|----------------|
| **Pixels** | 3700 | 1848 |
| **Library** | SeaBreeze | ftd2xx + SensorT.dll |
| **Data Type** | float64 | uint16 native |
| **Integration Unit** | milliseconds | microseconds |
| **Post-set Delay** | 0.3s (optional) | None (removed) |
| **Memory Pattern** | Allocate per scan | Pre-allocated buffer |
| **Thread Safety** | Not needed | Required (Lock) |
| **Calibration** | Built-in | External file |

---

## 11. References

- **Main Implementation**: `Phase Photonics Modifications/main/main.py` (lines 1481-1502)
- **API Core**: `Phase Photonics Modifications/utils/SpectrometerAPI.py`
- **USB4000 Adapter**: `Phase Photonics Modifications/utils/usb4000.py`
- **DLL Location**: `Phase Photonics Modifications/utils/SensorT_x64.dll`
- **Complete Analysis**: `PHASE_PHOTONICS_ANALYSIS.md`
- **Quick Start**: `PHASE_PHOTONICS_QUICK_START.md`

---

## 12. Contact

For Phase Photonics-specific questions:
- Refer to OEM-provided code in `Phase Photonics Modifications/`
- Check SpectrometerAPI.py for thread safety implementation
- Review main.py lines 1481-1502 for memory management pattern

**Last Updated**: Based on OEM guidance about memory management optimization (lines 1481-1502)
