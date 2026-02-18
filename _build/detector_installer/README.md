# Phase Photonics ST00012 Detector Installer

This installer package provides the necessary files to integrate the Phase Photonics ST00012 spectrometer/detector into any Python project.

## Contents

| File | Description |
|------|-------------|
| `install_detector.py` | Installation script |
| `Sensor64bit.dll` | Native driver library (64-bit Windows) |
| `phase_photonics_wrapper.py` | Python API wrapper using ctypes |

## Installation

### Option 1: Run the installer script

```bash
cd detector_installer
python install_detector.py /path/to/your/project
```

### Option 2: Manual installation

1. Copy `Sensor64bit.dll` to your project's `utils/` folder
2. Copy `phase_photonics_wrapper.py` to your project's `utils/` folder
3. Add to your `utils/__init__.py`:
   ```python
   from .phase_photonics_wrapper import SpectrometerAPI
   ```

## Quick Start

```python
from utils.phase_photonics_wrapper import SpectrometerAPI
import numpy as np

# Initialize API with path to DLL
api = SpectrometerAPI("./utils/Sensor64bit.dll")

# Connect to detector by serial number
handle = api.usb_initialize("ST00012")

if handle and handle.value:
    # Configure acquisition
    api.usb_set_interval(handle, 10000)   # Integration time: 10ms
    api.usb_set_averaging(handle, 1)       # No averaging
    
    # Read spectrum
    ret, spectrum = api.usb_read_pixels(handle)
    
    if ret == 0:
        print(f"Spectrum shape: {spectrum.shape}")
        print(f"Max intensity: {np.max(spectrum)}")
    
    # Disconnect
    api.usb_deinit(handle)
```

## Calibration (ST00012)

Convert pixel numbers to wavelengths using these polynomial coefficients:

```python
CALIBRATION_COEFFS = [
    536.2118491060357,      # c0
    0.10261733564399202,    # c1
    2.947529336201839e-06,  # c2
    -4.848287053280828e-09  # c3
]

def pixels_to_wavelength(pixels, coeffs):
    """λ = c0 + c1*x + c2*x² + c3*x³"""
    wavelengths = np.zeros_like(pixels, dtype=float)
    for i, c in enumerate(coeffs):
        wavelengths += c * (pixels ** i)
    return wavelengths

# Usage
pixels = np.arange(1848)  # Detector has 1848 pixels
wavelengths = pixels_to_wavelength(pixels, CALIBRATION_COEFFS)
```

## API Reference

### SpectrometerAPI Methods

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `usb_initialize(serial)` | Serial number string | Handle | Connect to device |
| `usb_deinit(handle)` | Device handle | int | Disconnect from device |
| `usb_read_pixels(handle)` | Device handle | (ret, np.array) | Read spectrum data |
| `usb_set_interval(handle, µs)` | Handle, microseconds | int | Set integration time |
| `usb_set_averaging(handle, n)` | Handle, count | int | Set averaging count |
| `usb_read_config(handle, area)` | Handle, area number | (ret, config) | Read calibration data |
| `usb_ping(handle)` | Device handle | int | Check device connection |
| `usb_dll_revision()` | None | (ret, revision) | Get DLL version |
| `usb_fw_revision(handle)` | Device handle | (ret, revision) | Get firmware version |

## Requirements

- Windows 64-bit
- Python 3.8+
- NumPy

## Troubleshooting

**"Failed to open device"**: Ensure the device is connected and the serial number is correct. Only one application can access the device at a time.

**"Could not find module"**: Make sure the DLL path is correct and FTDI drivers are installed.
