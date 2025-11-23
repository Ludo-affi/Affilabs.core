# PhasePhotonics DLL - Confirmed Location

## ✅ DLL Files Located

The PhasePhotonics detector DLL files are confirmed to be in:

```
Old software/Phase Photonics Modifications/utils/
├── SensorT_x64.dll  ✅ 64-bit DLL (RECOMMENDED)
└── Sensor.dll       ✅ 32-bit DLL (also available)
```

## 📦 Installation Instructions

### Option 1: PowerShell Script (Recommended)

Run the provided installation script:
```powershell
cd "Old software"
.\install_phase_photonics_dll.ps1
```

This script will:
- ✅ Verify source DLL exists
- ✅ Check for existing destination
- ✅ Copy DLL to utils folder
- ✅ Verify installation
- ✅ Display next steps

### Option 2: Manual Copy

From PowerShell in the `Old software` directory:
```powershell
Copy-Item "Phase Photonics Modifications\utils\SensorT_x64.dll" -Destination "utils\"
```

Or from Command Prompt:
```cmd
copy "Phase Photonics Modifications\utils\SensorT_x64.dll" "utils\"
```

### Option 3: File Explorer

1. Navigate to: `Old software\Phase Photonics Modifications\utils\`
2. Copy: `SensorT_x64.dll`
3. Paste to: `Old software\utils\`

## 🔧 Usage in Code

Once the DLL is copied to `utils/`, use it in the PhasePhotonics wrapper:

```python
from pathlib import Path
from .SpectrometerAPI import SpectrometerAPI

# In PhasePhotonics.__init__() or open():
dll_path = Path(__file__).parent / "SensorT_x64.dll"
self.api = SpectrometerAPI(str(dll_path))
```

The reference implementation also includes device-specific DLL selection:
```python
# From Phase Photonics Modifications/utils/usb4000.py lines 51-55
if self.serial_number == "ST00005":
    self.api = SpectrometerAPI(
        Path(__file__).parent / "SensorT_x64.dll",
    )
else:
    # Default to regular DLL
    self.api = SpectrometerAPI(
        Path(__file__).parent / "Sensor.dll",
    )
```

## ⚠️ Important Notes

1. **Do NOT copy DLL until ready to implement**
   - Keep utils folder clean during development
   - Only add DLL when implementing PhasePhotonics driver

2. **64-bit vs 32-bit**
   - Use `SensorT_x64.dll` for 64-bit Python (recommended)
   - Use `Sensor.dll` for 32-bit Python
   - Check with: `python -c "import sys; print(sys.maxsize > 2**32)"`
     - `True` = 64-bit (use SensorT_x64.dll)
     - `False` = 32-bit (use Sensor.dll)

3. **DLL Dependencies**
   - Requires FTDI drivers (ftd2xx)
   - Install with: `pip install ftd2xx`

4. **Testing**
   - Verify DLL loads: `self.api = SpectrometerAPI(dll_path)`
   - Test device enumeration: `from ftd2xx import listDevices`
   - Check device detection: `listDevices()` should show "ST*" devices

## 📋 Checklist

Before copying DLL:
- [ ] Read implementation documentation
- [ ] Understand PhasePhotonics interface
- [ ] Review reference code
- [ ] Install ftd2xx: `pip install ftd2xx`

After copying DLL:
- [ ] Verify file exists: `utils/SensorT_x64.dll`
- [ ] Update SpectrometerAPI.py (SENSOR_DATA_LEN = 1848)
- [ ] Implement methods in phase_photonics_wrapper.py
- [ ] Test DLL loading
- [ ] Test device enumeration
- [ ] Test full acquisition cycle

## 🔗 Related Documentation

- **Implementation Guide**: `PHASE_PHOTONICS_IMPLEMENTATION_SUMMARY.md`
- **Integration Details**: `PHASE_PHOTONICS_INTEGRATION.md`
- **Quick Start**: `PHASE_PHOTONICS_QUICK_START.md`
- **Configuration**: `DETECTOR_CONFIG_EXAMPLE.md`

---

**Status**: DLL location confirmed ✅
**Path**: `Phase Photonics Modifications/utils/SensorT_x64.dll`
**Ready**: Use install script when implementing
**Last Updated**: November 19, 2025
