# PhasePhotonics Detector - Quick Start Guide

## ✅ What's Done

The infrastructure for PhasePhotonics detector integration is complete:

1. **Placeholder wrapper**: `utils/phase_photonics_wrapper.py` ✅
2. **Detector selection**: `main/main.py` updated ✅
3. **Configuration system**: Uses `config.json` ✅
4. **Documentation**: Complete implementation guides ✅
5. **Safety**: USB4000 driver untouched ✅

## 🚀 Quick Configuration

### To Use USB4000 (Default - OceanOptics)
No changes needed! System defaults to USB4000.

Or explicitly set in `config.json`:
```json
{
  "detector_type": "USB4000"
}
```

### To Test PhasePhotonics Placeholder
Edit `config.json`:
```json
{
  "detector_type": "PhasePhotonics"
}
```

⚠️ **Note**: PhasePhotonics is currently a placeholder. It will log warnings and not connect to hardware.

## 📚 Documentation Files

| File | Purpose |
|------|---------|
| `PHASE_PHOTONICS_IMPLEMENTATION_SUMMARY.md` | Start here - complete overview |
| `PHASE_PHOTONICS_INTEGRATION.md` | Detailed implementation guide |
| `DETECTOR_CONFIG_EXAMPLE.md` | Quick config examples |

## 🔧 For Implementation

### What You Need
1. **Reference code**: `Phase Photonics Modifications/utils/usb4000.py`
2. **Modified API**: `Phase Photonics Modifications/utils/SpectrometerAPI.py`
3. **Target file**: `utils/phase_photonics_wrapper.py` (replace placeholders)
4. **DLL files**:
   - 64-bit: `Phase Photonics Modifications/utils/SensorT_x64.dll` ✅
   - 32-bit: `Phase Photonics Modifications/utils/Sensor.dll` ✅
   - Copy to: `utils/` folder

### Key Implementation Points
```python
# 1. Update SENSOR_DATA_LEN
SENSOR_DATA_LEN = 1848  # Not 3700!

# 2. Use ftd2xx for device enumeration
from ftd2xx import listDevices
devs = [s.decode() for s in listDevices() if s.startswith(b"ST")]

# 3. Required delay after set_integration
r = self.api.usb_set_interval(self.spec, int(integration_ms * 1000))
# No delay needed (removed per user request)

# 4. Set placeholder flag when done
IS_PLACEHOLDER = False
```

### Testing Before Production
```python
# Simple test
from utils.phase_photonics_wrapper import PhasePhotonics
pp = PhasePhotonics()
assert pp.open() == True
assert len(pp.read_wavelength()) == 1848
```

## ⚠️ Important Warnings

### DO NOT
- ❌ Modify `utils/usb4000_wrapper.py` (USB4000 driver)
- ❌ Replace USB4000 files
- ❌ Set PhasePhotonics in production before full testing

### DO
- ✅ Keep both detectors as separate files
- ✅ Test PhasePhotonics thoroughly in isolation
- ✅ Verify USB4000 still works after SpectrometerAPI changes
- ✅ Update documentation when implementation complete

## 🎯 Current Status

**Infrastructure**: ✅ Complete
**PhasePhotonics Driver**: ⚠️ Placeholder only
**USB4000 Driver**: ✅ Production ready
**Risk**: 🟢 Low (isolated implementation)

## 📞 Next Steps

1. **Review** reference implementation in `Phase Photonics Modifications/`
2. **Read** `PHASE_PHOTONICS_IMPLEMENTATION_SUMMARY.md`
3. **Implement** methods in `utils/phase_photonics_wrapper.py`
4. **Test** thoroughly before production
5. **Deploy** with `detector_type` configuration

---

**Ready to implement!** All infrastructure in place. See full documentation for detailed implementation guide.
