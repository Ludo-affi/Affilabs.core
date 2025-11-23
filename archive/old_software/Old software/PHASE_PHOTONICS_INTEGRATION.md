# PhasePhotonics Detector Integration - PLACEHOLDER DOCUMENTATION

## Overview

A placeholder has been added for the **PhasePhotonics detector** that will replace the current USB4000 (OceanOptics) detector. The system now supports both detectors through a configuration option.

## Current Status

⚠️ **PLACEHOLDER IMPLEMENTATION** - PhasePhotonics detector is not yet fully implemented.

### What's Ready
- ✅ Placeholder class created: `utils/phase_photonics_wrapper.py`
- ✅ Interface matches USB4000 for drop-in compatibility
- ✅ Configuration system supports detector selection
- ✅ Main application can initialize either detector

### What Needs Implementation
- ❌ Actual PhasePhotonics API integration
- ❌ SensorT.dll loading and initialization
- ❌ Device enumeration and connection
- ❌ Spectrum acquisition
- ❌ Wavelength calibration
- ❌ Integration time control

## Switching Between Detectors

### Method 1: Configuration File (Recommended)

Edit `config.json` in the application root directory:

```json
{
  "detector_type": "USB4000",
  ...other settings...
}
```

**Options:**
- `"USB4000"` - Uses OceanOptics USB4000/FLAME-T detector (default)
- `"PhasePhotonics"` - Uses PhasePhotonics detector (placeholder)

### Method 2: Default Fallback

If `detector_type` is not specified in config.json, the system defaults to `"USB4000"`.

## Implementation Guide

### Reference Files

The PhasePhotonics modifications folder contains working reference code:
- **Phase Photonics Modifications/utils/usb4000.py** - Working implementation
- **Phase Photonics Modifications/utils/SpectrometerAPI.py** - Modified API with threading

### Key Differences: PhasePhotonics vs USB4000

| Feature | USB4000 (OceanOptics) | PhasePhotonics |
|---------|----------------------|----------------|
| **Library** | SeaBreeze (pyseabreeze) | SensorT.dll (ctypes) |
| **Data Points** | 3700 pixels | 1848 pixels |
| **Connection** | USB via WinUSB driver | FTDI FT245 (ftd2xx) |
| **Device ID** | Ocean Optics serial | Serial starts with "ST" |
| **Integration Units** | Microseconds | Microseconds (ms × 1000) |
| **Post-Set Delay** | Immediate | None (delay removed) |

### Implementation Steps

1. **Copy Reference Implementation**
   ```python
   # From: Phase Photonics Modifications/utils/usb4000.py
   # To: utils/phase_photonics_wrapper.py
   ```

2. **Update SpectrometerAPI**
   ```python
   # Review differences in:
   # - Phase Photonics Modifications/utils/SpectrometerAPI.py
   # - Old software/utils/SpectrometerAPI.py
   #
   # Key changes:
   # - SENSOR_DATA_LEN = 1848 (not 3700)
   # - Added threading.Lock for thread safety
   # - Modified structure packing (_pack_ = 1, _layout_ = "ms")
   ```

3. **Install Dependencies**
   ```bash
   pip install ftd2xx  # FTDI driver for PhasePhotonics
   pip install numpy
   ```

4. **Update Constants**
   ```python
   # In utils/phase_photonics_wrapper.py
   IS_PLACEHOLDER = False  # Set to False when implemented
   ```

5. **Test Thoroughly**
   - Device enumeration
   - Connection/disconnection
   - Spectrum acquisition
   - Wavelength calibration
   - Integration time settings
   - Thread safety under load

### Required DLL Files

**Location Confirmed**:
- **64-bit DLL**: `Phase Photonics Modifications/utils/SensorT_x64.dll` ✅
- **32-bit DLL**: `Phase Photonics Modifications/utils/Sensor.dll` ✅

**Installation**:
Copy the appropriate DLL from the Phase Photonics Modifications folder to the main utils folder:

```powershell
# From PowerShell in 'Old software' directory:
Copy-Item "Phase Photonics Modifications/utils/SensorT_x64.dll" -Destination "utils/"
```

The code will automatically select the correct DLL based on device serial number (see reference implementation in `Phase Photonics Modifications/utils/usb4000.py` lines 51-55).

## Interface Compatibility

The placeholder maintains the same interface as USB4000 to ensure no changes are needed in the main application:

### Required Methods
```python
def open() -> bool
def close() -> None
def set_integration(integration_ms: float) -> bool
def read_wavelength() -> np.ndarray
def read_spectrum() -> np.ndarray
def read_intensity() -> float
def wavelengths() -> np.ndarray
```

### Required Properties
```python
self.opened: bool
self.serial_number: str
self.spec: object  # Device handle
self.min_integration: float  # seconds
self.max_integration: float  # seconds
```

## Safety Considerations

⚠️ **IMPORTANT**: The current `utils/usb4000_wrapper.py` must **NOT** be modified or replaced. It is the only working connection to the USB4000/OceanOptics detector.

Instead:
1. ✅ Keep `utils/usb4000_wrapper.py` unchanged
2. ✅ Implement PhasePhotonics in separate file `utils/phase_photonics_wrapper.py`
3. ✅ Switch via configuration, not by replacing files
4. ✅ Test PhasePhotonics thoroughly before production use

## Testing Checklist

Before deploying PhasePhotonics detector:

- [ ] Device enumeration works (finds "ST*" devices)
- [ ] Connection succeeds (usb_initialize returns valid handle)
- [ ] Wavelength calibration loads correctly (1848 points)
- [ ] Spectrum acquisition works (read_spectrum returns data)
- [ ] Integration time setting works (with 0.3s delay)
- [ ] Multiple acquire cycles work without crashes
- [ ] Thread safety verified (no race conditions)
- [ ] Error handling works (device disconnect, timeouts)
- [ ] Memory leaks checked (device handle cleanup)
- [ ] Performance acceptable (acquisition speed)

## Troubleshooting

### PhasePhotonics Not Detected
- Check FTDI drivers installed (ftd2xx)
- Verify device serial starts with "ST"
- Check SensorT.dll is in utils folder
- Confirm USB connection

### USB4000 Not Working After Changes
- Verify config.json has `"detector_type": "USB4000"`
- Check utils/usb4000_wrapper.py not modified
- Verify pyseabreeze installed
- Check WinUSB driver via Zadig

## Contact & Support

For PhasePhotonics implementation questions:
- Reference: Phase Photonics Modifications folder
- Modified API: SpectrometerAPI.py in modifications folder
- Original USB4000: utils/usb4000_wrapper.py (DO NOT MODIFY)

---

**Status**: PLACEHOLDER - Awaiting full implementation
**Last Updated**: November 19, 2025
