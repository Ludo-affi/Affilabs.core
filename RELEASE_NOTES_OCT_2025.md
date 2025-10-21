# Release Notes - October 21, 2025

## Version 3.2.9 - Production Ready Release

### 🎉 Major Achievements

This release marks the completion of all critical bug fixes and represents a **production-ready** state of the ezControl-AI SPR control system.

---

## ✅ Issues Resolved

### 1. **Calibration Saturation Bug** (CRITICAL FIX)
**Problem**: Calibration failed during Step 4 validation due to saturation. The binary search tested the strongest channel at LED=25 but then measured all channels at their individually predicted higher LED values (60-128), causing saturation.

**Solution**: 
- Modified `utils/spr_calibrator.py` (lines 2366-2420)
- Binary search now tests ALL channels at their predicted LED values during each iteration
- Finds maximum signal across all channels
- Uses highest signal for saturation constraint checking
- Validation now uses the same LED values that were tested

**Impact**: ✅ Calibration completes successfully without saturation warnings

---

### 2. **Python Version Management** (CRITICAL FIX)
**Problem**: System kept reverting to Python 3.9 without notice, causing typing errors with `|` union operators.

**Solution**: Implemented 5-layer protection system:
1. **Launcher Scripts**: `run_app_312.ps1` and `run_app_312.bat` force Python 3.12
2. **VS Code Config**: `.vscode/settings.json` defaults to `.venv312`
3. **Execution Block**: `main/main.py` blocks execution if Python < 3.12
4. **Logger Warning**: `utils/logger.py` shows massive ASCII warning banner
5. **Runtime Banner**: Displays Python version on every startup

**Files Created**:
- `run_app_312.ps1` - PowerShell launcher (PRIMARY METHOD)
- `run_app_312.bat` - Batch file launcher
- `PYTHON_312_REQUIREMENT.md` - User documentation
- `PYTHON_VERSION_ENFORCEMENT.md` - Technical documentation
- `utils/python_version_check.py` - Version validation module

**Impact**: ✅ Python 3.12.10 running consistently, no more silent version switches

---

### 3. **Dark Noise Warning Correction**
**Problem**: STEP 1 showed misleading dark noise warnings using hardcoded value of 400 instead of detector profile baseline (3500 for USB4000).

**Solution**:
- Modified `utils/spr_calibrator.py` (lines 3146-3180)
- Now uses detector profile `dark_noise_mean_counts` (3500 for USB4000)
- Changed wording from "Dark noise" to "Raw dark noise mean"
- Only warns if signal exceeds 5× the profile baseline

**Impact**: ✅ Warnings now accurate for USB4000 detector, reduced false alarms

---

### 4. **Polarizer Warning Threshold**
**Problem**: Polarizer warning triggered too early at 3.0× ratio difference, not matching user's hardware.

**Solution**:
- Modified `utils/spr_calibrator.py` (line 1970)
- Changed `IDEAL_RATIO_MIN` from 3.0 to 1.33
- Now triggers warning only if ratio < 1.33× (instead of 3.0×)

**Impact**: ✅ Reduced false polarizer warnings, matches actual hardware performance

---

### 5. **UI Cleanup**
**Problem**: Diagnostic viewer (4-graph window) was a development tool no longer needed in production.

**Solution**:
- Removed diagnostic viewer button and functionality from `widgets/mainwindow.py`
- Removed `DiagnosticViewer` import and all related code
- Cleaned up toolbar

**Impact**: ✅ Cleaner UI focused on production features

---

## 📝 Documentation Updates

### New Documentation Files
1. **CURRENT_STATUS.md** - Comprehensive system status document
   - Complete overview of all fixes
   - System architecture details
   - Usage instructions and troubleshooting
   - Technical specifications

2. **PYTHON_312_REQUIREMENT.md** - Python version requirements
   - Why Python 3.12 is required
   - How to verify correct version
   - Troubleshooting version issues

3. **PYTHON_VERSION_ENFORCEMENT.md** - Technical implementation
   - 5-layer protection system details
   - Code locations and mechanisms
   - Testing procedures

### Updated Documentation
1. **README.md** - Complete rewrite
   - Quick start guide
   - Python 3.12 enforcement instructions
   - Calibration overview (8 steps)
   - Troubleshooting guide
   - Current system status

---

## 🚀 System Status

### Hardware Support
- ✅ USB4000 spectrometer (Ocean Optics via seabreeze)
- ✅ PicoP4SPR 4-channel controller
- ✅ Cavro pump integration
- ✅ Temperature monitoring

### Software Status
- ✅ Python 3.12.10 enforced
- ✅ All typing errors resolved
- ✅ Calibration stable (8-step process)
- ✅ Live mode running at ~1.2 Hz
- ✅ Sensorgram display for all 4 channels
- ✅ Automatic saturation prevention
- ✅ No false warnings

### Performance Metrics
- **Calibration Time**: 5-10 minutes
- **Live Acquisition Rate**: 1.18 Hz (850ms/cycle)
- **Spectrum Acquisition**: ~60ms each (12 per cycle)
- **No saturation warnings** during 68+ cycle validation run
- **Stable operation** confirmed

---

## 🎯 How to Use

### Starting the Application
```powershell
# RECOMMENDED: Use the launcher script
.\run_app_312.ps1
```

The launcher will:
1. Verify Python 3.12 is being used
2. Activate the correct virtual environment
3. Display Python version confirmation
4. Start the application

### First-Time Calibration
1. Connect USB4000 spectrometer (USB)
2. Connect PicoP4SPR controller (COM port)
3. Launch with `.\run_app_312.ps1`
4. Click "Settings" → "Calibration"
5. Follow 8-step calibration wizard
6. Wait for "Calibration Complete" message
7. Start live mode from Sensorgram view

---

## 🔧 Technical Changes

### Modified Files
- `widgets/mainwindow.py` - Removed diagnostic viewer
- `utils/spr_calibrator.py` - Fixed Step 4, dark noise, polarizer threshold
- `main/main.py` - Added Python version enforcement
- `utils/logger.py` - Added version check warning
- `README.md` - Complete documentation update
- `.vscode/settings.json` - Force Python 3.12

### New Files
- `run_app_312.ps1` - Primary launcher
- `run_app_312.bat` - Alternative launcher
- `utils/python_version_check.py` - Version validation
- `CURRENT_STATUS.md` - System documentation
- `PYTHON_312_REQUIREMENT.md` - User guide
- `PYTHON_VERSION_ENFORCEMENT.md` - Technical guide
- `RELEASE_NOTES_OCT_2025.md` - This file

---

## 🐛 Known Limitations

### Current System
- Windows only (requires WinUSB drivers)
- Single spectrometer support (USB4000)
- Serial COM port required for PicoP4SPR

### Performance
- Acquisition speed limited by spectrometer integration time
- ~60ms per spectrum (normal with typical integration times)
- 4 fixed channels (a, b, c, d)

---

## 🔮 Future Enhancements (Potential)

- Multi-spectrometer support (QEPro, Flame-S)
- Network-based device control
- Advanced data export formats
- Automated system health monitoring
- Plugin system for custom detectors

---

## 📊 Validation Summary

### Test Results
- ✅ Calibration completes without saturation (8 steps)
- ✅ Live mode runs stably (68+ cycles validated)
- ✅ Python 3.12 enforced (no accidental version switches)
- ✅ All 4 channels displaying correctly
- ✅ No spurious warnings
- ✅ Hardware detection working
- ✅ Emergency stop functional

### Code Quality
- ✅ Python 3.12 type hints throughout
- ✅ Comprehensive error handling
- ✅ Extensive logging
- ✅ Modular architecture
- ✅ Clean separation of concerns

---

## 👥 Credits

- **Development**: AI-enhanced development with human oversight
- **Testing**: Production hardware validation
- **Documentation**: Comprehensive user and technical guides

---

## 📞 Support

### For Issues
1. Check `CURRENT_STATUS.md` for system overview
2. Review `README.md` troubleshooting section
3. Verify Python 3.12 with `.\run_app_312.ps1`
4. Check hardware connections (Device Manager)
5. Review terminal logs for errors

### Common Solutions
- **USB4000 not detected**: Unplug/replug, check WinUSB drivers
- **Python version errors**: Always use `run_app_312.ps1` launcher
- **Calibration issues**: Ensure proper sample alignment
- **Slow acquisition**: Normal at ~60ms per spectrum

---

## ✨ Summary

The ezControl-AI system is now **fully operational and production-ready** with all critical issues resolved:

1. ✅ **Saturation bug fixed** - Calibration and live mode stable
2. ✅ **Python 3.12 enforced** - No more version confusion
3. ✅ **Dark noise warnings corrected** - Accurate detector profiles
4. ✅ **Polarizer threshold adjusted** - Reduced false alarms
5. ✅ **UI cleaned up** - Removed diagnostic viewer

**System validated and ready for production SPR measurements!** 🚀

---

*Release Date: October 21, 2025*
*Version: 3.2.9*
*Status: Production Ready*
