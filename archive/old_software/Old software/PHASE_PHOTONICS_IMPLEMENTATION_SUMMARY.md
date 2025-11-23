# PhasePhotonics Detector Integration - Implementation Summary

## ✅ Completed

### 1. Placeholder Wrapper Created
**File**: `utils/phase_photonics_wrapper.py`

- Complete interface matching USB4000 for drop-in compatibility
- All required methods stubbed with TODO comments
- Extensive documentation for each method
- Reference implementation notes included
- Thread-safe placeholder implementation

### 2. Main Application Updated
**File**: `main/main.py`

- Added PhasePhotonics import
- Detector selection via configuration
- Defaults to USB4000 (safe fallback)
- Logging shows which detector is being used
- Zero impact on existing USB4000 functionality

### 3. Configuration System
**Detection Method**: `config.json` → `detector_type` field

```json
{
  "detector_type": "USB4000"  // or "PhasePhotonics"
}
```

- ✅ USB4000: Production ready, default
- ⚠️ PhasePhotonics: Placeholder only

### 4. Documentation Created

**Primary Documentation**:
- `PHASE_PHOTONICS_INTEGRATION.md` - Complete implementation guide

**Quick Reference**:
- `DETECTOR_CONFIG_EXAMPLE.md` - Configuration examples

## 🔒 Safety Guarantees

### USB4000 Protection
✅ **Original `utils/usb4000_wrapper.py` is UNTOUCHED**
- No modifications to working USB4000 driver
- Existing OceanOptics functionality preserved
- Separate file for PhasePhotonics avoids conflicts

### Backward Compatibility
✅ **Existing systems continue working**
- Defaults to USB4000 if no config specified
- No breaking changes to existing code
- Same interface for both detectors

## 📋 Next Steps for Implementation

### Phase 1: Review Reference Code
1. Study `Phase Photonics Modifications/utils/usb4000.py`
2. Compare `Phase Photonics Modifications/utils/SpectrometerAPI.py` with current version
3. Identify key differences in DLL interface

### Phase 2: Update SpectrometerAPI.py
**Key Changes Needed**:
```python
# From original: SENSOR_DATA_LEN = 3700
# To PhasePhotonics: SENSOR_DATA_LEN = 1848

# Add threading support:
from threading import Lock

# Update structure packing:
class config_contents(ctypes.Structure):
    _pack_ = 1
    _layout_ = "ms"
    _fields_ = [("data", ctypes.c_uint8 * CONFIG_DATA_AREA_SIZE)]
```

⚠️ **CRITICAL**: Test this doesn't break USB4000!

### Phase 3: Implement PhasePhotonics Wrapper
Replace placeholder methods in `utils/phase_photonics_wrapper.py`:

1. **Device Enumeration** (uses ftd2xx)
   ```python
   from ftd2xx import listDevices
   self.devs = [s.decode() for s in listDevices() if s.startswith(b"ST")]
   ```

2. **Connection** (uses SpectrometerAPI)
   ```python
   from .SpectrometerAPI import SpectrometerAPI
   self.api = SpectrometerAPI(Path(__file__).parent / "SensorT.dll")
   self.spec = self.api.usb_initialize(serial_number)
   ```

3. **Wavelength Calibration**
   ```python
   bytes_read, config = self.api.usb_read_config(self.spec, 0)
   coeffs = frombuffer(config.data, ">f8", 4, 3072)
   calibration_curve = Polynomial(coeffs)
   return calibration_curve(arange(1848))  # Note: 1848 not 3700
   ```

4. **Set Integration Time** (with required delay)
   ```python
   r = self.api.usb_set_interval(self.spec, int(integration_ms * 1000))
   sleep(0.3)  # REQUIRED: PhasePhotonics needs 0.3s delay
   ```

### Phase 4: Install Dependencies
```bash
pip install ftd2xx  # FTDI driver for PhasePhotonics
```

### Phase 5: Add DLL Files

**DLL Location Confirmed**:
- Source: `Phase Photonics Modifications/utils/SensorT_x64.dll` ✅
- Also available: `Phase Photonics Modifications/utils/Sensor.dll` (32-bit)

**Installation**:
Copy the appropriate DLL to the main utils folder:
```powershell
# For 64-bit (recommended)
Copy-Item "Phase Photonics Modifications/utils/SensorT_x64.dll" -Destination "utils/"

# OR for 32-bit
Copy-Item "Phase Photonics Modifications/utils/Sensor.dll" -Destination "utils/"
```

**In Code**:
```python
from pathlib import Path
dll_path = Path(__file__).parent / "SensorT_x64.dll"
self.api = SpectrometerAPI(str(dll_path))
```

### Phase 6: Testing Protocol
```python
# Test in isolation first
from utils.phase_photonics_wrapper import PhasePhotonics
pp = PhasePhotonics()
assert pp.open() == True
assert pp.read_wavelength() is not None
assert len(pp.read_wavelength()) == 1848
assert pp.read_spectrum() is not None
```

### Phase 7: Integration Testing
1. Set `config.json`: `"detector_type": "PhasePhotonics"`
2. Launch application
3. Verify device connects
4. Verify calibration works
5. Verify spectrum acquisition
6. Test under load (continuous acquisition)
7. Check thread safety

### Phase 8: Production Deployment
1. Update `IS_PLACEHOLDER = False` in wrapper
2. Update documentation with actual usage
3. Create migration guide for users
4. Add troubleshooting section

## 🎯 Key Implementation Points

### Critical Differences: USB4000 vs PhasePhotonics

| Feature | USB4000 | PhasePhotonics |
|---------|---------|----------------|
| Library | SeaBreeze | ctypes + SensorT.dll |
| Pixels | 3700 | 1848 |
| Connection | pyseabreeze | ftd2xx |
| Device ID | Ocean Optics S/N | Serial "ST*" |
| Post-Set Delay | None | None (removed) |

### Thread Safety
Both detectors must support concurrent access:
- Acquisition thread reading spectra
- UI thread updating settings
- Processing thread analyzing data

Reference implementation uses `threading.Lock()` - verify this is implemented.

### Error Handling
Must handle gracefully:
- Device not found
- Connection timeout
- Read failures
- Integration time out of bounds
- Device disconnect during operation

## 📁 File Structure

```
Old software/
├── utils/
│   ├── usb4000_wrapper.py          ✅ UNCHANGED (USB4000)
│   ├── phase_photonics_wrapper.py  ⚠️ PLACEHOLDER (PhasePhotonics)
│   ├── SpectrometerAPI.py          ⚠️ NEEDS UPDATE for PhasePhotonics
│   └── SensorT_x64.dll             ❌ NOT INCLUDED (copy when implementing)
│
├── main/
│   └── main.py                     ✅ UPDATED (detector selection)
│
├── Phase Photonics Modifications/  📚 REFERENCE CODE
│   └── utils/
│       ├── usb4000.py              ✅ Working PhasePhotonics implementation
│       ├── SpectrometerAPI.py      ✅ Modified for PhasePhotonics
│       ├── SensorT_x64.dll         ✅ 64-bit DLL (CONFIRMED PATH)
│       └── Sensor.dll              ✅ 32-bit DLL (also available)
│
├── Documentation:
│   ├── PHASE_PHOTONICS_IMPLEMENTATION_SUMMARY.md  📖 Full guide
│   ├── PHASE_PHOTONICS_INTEGRATION.md             📖 Implementation details
│   ├── PHASE_PHOTONICS_QUICK_START.md             📖 Quick reference
│   └── DETECTOR_CONFIG_EXAMPLE.md                 📖 Config examples
│
└── install_phase_photonics_dll.ps1 🔧 Helper script to copy DLL
```

## ⚠️ Important Warnings

### DO NOT Modify These Files (USB4000 Protection)
- ❌ `utils/usb4000_wrapper.py` - Working USB4000 driver
- ❌ Existing calibration files
- ❌ Production config.json (unless testing)

### MUST Verify Before Production
- ✅ Thread safety under load
- ✅ Memory leak testing (device handle cleanup)
- ✅ Error recovery (device disconnect)
- ✅ Performance benchmarks
- ✅ Wavelength calibration accuracy

### Testing Checklist
Before setting `IS_PLACEHOLDER = False`:

- [ ] Device enumeration works
- [ ] Connection/disconnection stable
- [ ] Wavelength calibration loads (1848 points)
- [ ] Spectrum acquisition successful
- [ ] Integration time setting works (with 0.3s delay)
- [ ] Multiple cycles work (100+ acquisitions)
- [ ] Thread safety verified
- [ ] Error handling tested
- [ ] Memory leaks checked
- [ ] Performance acceptable
- [ ] USB4000 still works after changes

## 📞 Questions & Support

**For Implementation**:
1. Review `Phase Photonics Modifications/` folder
2. Check `PHASE_PHOTONICS_INTEGRATION.md`
3. Reference methods in placeholder (extensive TODO comments)

**For Configuration**:
1. Check `DETECTOR_CONFIG_EXAMPLE.md`
2. Modify `config.json` → `detector_type`

**For USB4000 Issues**:
1. Verify `detector_type: "USB4000"` in config
2. Check `utils/usb4000_wrapper.py` not modified
3. Verify SeaBreeze installed

---

**Status**: ✅ Placeholder infrastructure complete, ready for implementation
**Estimated Implementation Time**: 1-2 days for experienced developer
**Risk Level**: LOW (isolated implementation, USB4000 protected)
**Last Updated**: November 19, 2025
