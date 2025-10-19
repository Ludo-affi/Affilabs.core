# Affilabs 0.1 - Version History

## Version 0.1.0 (2025-10-19) - Foundation Release 🎉

**"The Core"** - First stable release establishing the foundation of Affilabs SPR technology.

### Major Features

#### 1. **Complete SPR Calibration System**
- 8-step automated calibration sequence
- Detector-agnostic architecture (Flame-T, USB4000, etc.)
- Dynamic integration time optimization
- Per-channel LED intensity balancing
- Dark noise measurement with afterglow correction
- Spectral filtering for SPR-relevant wavelength range (580-720nm)

#### 2. **Polarizer Management System**
- ✅ OEM calibration tool for barrel polarizer characterization
- ✅ Single source of truth for S/P positions in device_config.json
- ✅ Automated polarizer position validation (S/P ratio check)
- ✅ Correct SPR physics implementation (S=HIGH reference, P=LOWER resonance)
- ✅ Transmittance calculation: P/S ratio showing resonance dip

#### 3. **Live SPR Measurements**
- Real-time data acquisition (~1.2 Hz)
- 4-channel simultaneous measurement (a, b, c, d)
- Adaptive peak detection (630-650nm range)
- Temperature monitoring and logging
- Auto-start after successful calibration

#### 4. **Hardware Abstraction Layer**
- Unified interface for PicoP4SPR and PicoEZSPR devices
- Batch LED control commands for faster operation
- Robust serial communication with automatic recovery
- Pump integration support (Cavro XCalibur)

#### 5. **Data Processing Pipeline**
- Smart denoising (spectral filtering + median filtering)
- Transmittance spectrum calculation with dark noise subtraction
- Peak detection with adaptive wavelength range
- Metadata-rich data export for analysis

### Critical Fixes in 0.1.0

#### Polarizer Position Loading (RESOLVED)
**Problem**: Polarizer positions not being passed from config to calibration
- `device_config` parameter passed but never stored in SPRCalibrator
- Import path incorrect in spr_state_machine.py
- Config merge logic dropping oem_calibration section

**Solution**:
- Added `self.device_config = device_config` storage
- Fixed import: `utils.device_configuration` not `config.device_config`
- Fixed _merge_with_defaults() to preserve custom sections

#### Inverted Transmittance & Saturation (RESOLVED)
**Problem**: Transmittance showed peak instead of dip, P-mode saturating
- Root cause: S and P positions SWAPPED in device_config.json
- S=50 (LOW signal) used as reference → poor quality
- P=165 (HIGH signal) used for measurement → saturation

**Solution**:
- Swapped positions: S=165 (HIGH), P=50 (LOWER)
- Corrected all SPR physics documentation
- Fixed validation logic to check S/P ratio (not P/S)
- Result: Correct resonance dip, no saturation

### System Requirements
- Python 3.11-3.12
- Windows (PowerShell)
- PySide6 for GUI
- Serial communication (pyserial)
- Ocean Optics spectrometer support (oceandirect)

### Hardware Compatibility
- **SPR Controllers**: PicoP4SPR, PicoEZSPR
- **Spectrometers**: Flame-T, USB4000 (Ocean Optics)
- **Polarizers**: Barrel polarizer (2 fixed windows), rotating polarizer
- **Pumps**: Cavro XCalibur (optional)

### Known Limitations
- High dark noise (~3000 counts) - system compensates via subtraction
- Auto-save profile fails if positions not in state early enough (minor)
- Development mode bypasses some validation checks

### Documentation
- ✅ POLARIZER_POSITION_FIX_COMPLETE.md - Complete fix documentation
- ✅ OEM_CALIBRATION_TOOL_GUIDE.md - Polarizer setup instructions
- ✅ HARDWARE_MANAGEMENT_SYSTEM.md - HAL documentation
- ✅ DETECTOR_PROFILES_IMPLEMENTATION.md - Detector agnostic design
- ✅ CALIBRATION_ACCELERATION_GUIDE.md - Optimization strategies

### Next Steps (Future Releases)
- Multi-device support (concurrent measurements)
- Cloud data storage and analysis
- Machine learning for peak detection
- Advanced pump protocols
- Real-time kinetics analysis
- Web-based remote monitoring

---

## Development Philosophy

**Affilabs 0.1** establishes three core principles:

1. **Single Source of Truth**: OEM calibration determines polarizer positions empirically
2. **Hardware Agnostic**: System adapts to different detectors and configurations
3. **User-Centric**: Automatic calibration, intelligent defaults, minimal manual intervention

This release represents the stable foundation upon which Affilabs will build advanced SPR analysis capabilities.

---

**Release Date**: October 19, 2025  
**Commit**: `1bff6f6`  
**Branch**: `master`  
**Status**: ✅ Production Ready
