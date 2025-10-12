# Workspace Cleanup & GitHub Push Plan
**Date**: October 11, 2025

---

## 🎯 Objectives

1. **Clean workspace** - Remove diagnostic/test files, consolidate documentation
2. **Push to GitHub** - Commit device configuration system
3. **Prepare for main integration** - Clear path for optimization work

---

## 📋 Files to DELETE (Diagnostics & Old Tests)

### Test Scripts (Not needed in production):
- `analyze_dark_correction.py`
- `benchmark_batch_processing.py`
- `check_dark_noise.py`
- `check_npz_contents.py`
- `diagnostic_wavelength_ranges.py`
- `flame_t_feature_discovery.py`
- `led_timing_diagnostic.py`
- `led_timing_diagnostic_batch.py`
- `pico_batch_command_diagnostic.py`
- `quick_batch_test.py`
- `quick_dark_diagnostic.py`
- `realtime_batch_monitor.py`
- `scan_batch_performance_test.py`
- `test_batch_led_control.py`
- `test_first_scan_quality.py`
- `test_hardware_detection.py`
- `test_led_functionality.py`
- `test_sequential_4led.py`

### Test Results & Images:
- `led_continuous_cycles.png`
- `led_continuous_cycles_results.json`
- `led_functionality_test_100ms.png`
- `led_functionality_test_10ms.png`
- `led_functionality_test_50ms.png`
- `led_sequential_4led_cycles.png`
- `led_sequential_4led_results.json`
- `led_timing_analysis.png`
- `led_timing_batch_results.json`
- `led_timing_batch_results.png`
- `led_timing_results.json`
- `pico_batch_command_results.json`
- `benchmark_results/` (entire directory)

### Old Documentation (Superseded):
- `BATCH_LED_CONTROL_IMPLEMENTATION.md`
- `BATCH_LED_CONTROL_QUICK_REFERENCE.md`
- `BATCH_SCAN_PROCESSING_ANALYSIS.md`
- `COMPLETE_OPTIMIZATION_WORKFLOW.md`
- `CPU_SIDE_PROCESSING_OPTIMIZATIONS.md`
- `DARK_LED_OFF_FIX.md`
- `DARK_NOISE_FLOW_ANALYSIS.md`
- `FIRST_SCAN_QUALITY_ANALYSIS.md`
- `IMPLEMENTATION_TODO.md`
- `INTEGRATION_TIME_FIX.md`
- `INTEGRATION_TIME_SATURATION_FIX.md`
- `LED_MINIMUM_INTENSITY_FIX.md`
- `LED_TIMING_DIAGNOSTIC_BATCH_RESULTS.md`
- `PHASE_1_3_AND_2_1_COMPLETION.md`
- `PHASE_1_4_BENCHMARK_RESULTS.md`
- `PHASE_1_COMPLETION_SUMMARY.md`
- `PHASE_2_COMPLETION.md`
- `P_MODE_MEASUREMENT_SEQUENCE.md`
- `P_MODE_SIGNAL_BASED_BOOST.md`
- `P_MODE_SIMPLIFIED_CALIBRATION.md`
- `S_MODE_REFERENCE_FLOW_ANALYSIS.md`
- `CONFIGURATION_ANSWER.md` (superseded by other docs)
- `DEVICE_CONFIGURATION_QUICK_REF.md` (duplicate)

### Unused Utils:
- `utils/adaptive_batch_processor.py` (if not used)
- `utils/optimized_batch_processor.py` (if not integrated)
- `utils/usb_spectrometer.py` (if not used)
- `utils/config_cli.py` (if CLI not needed)
- `tests/test_optimized_batch_processor.py`

---

## ✅ Files to KEEP & ADD to Git

### New Device Configuration System:
- ✅ `widgets/device_settings.py` - **NEW GUI widget**
- ✅ `utils/hardware_detection.py` - **Hardware auto-detection**
- ✅ `utils/device_configuration.py` - **Config management**
- ✅ `utils/calibration_data_loader.py` - **Calibration loading**
- ✅ `factory_provision_device.py` - **Factory provisioning**
- ✅ `install_config.py` - **Customer installer**
- ✅ `setup_device.py` - **Device setup utility**

### Essential Documentation (Keep & Add):
- ✅ `DEVICE_DEPLOYMENT_GUIDE.md` - **Comprehensive deployment guide**
- ✅ `DEPLOYMENT_QUICK_SUMMARY.md` - **Quick reference**
- ✅ `CONFIG_QUICK_REFERENCE.md` - **Config file reference**
- ✅ `HARDWARE_DETECTION_FIX.md` - **SeaBreeze fix documentation**
- ✅ `CALIBRATION_ACCELERATION_GUIDE.md` - **Calibration optimization**
- ✅ `CALIBRATION_DATA_PERSISTENCE_COMPLETE.md` - **Calibration system**
- ✅ `FRESH_CALIBRATION_GUARANTEE.md` - **Fresh calibration strategy**
- ✅ `TIMING_PARAMETERS_INTEGRATION_COMPLETE.md` - **Timing parameters**

### Modified Files (Commit Changes):
- ✅ `widgets/settings_menu.py` - Added Device Configuration tab
- ✅ Modified core files (already tracked)

### Config Directory:
- ✅ `config/` - Keep directory structure (don't commit actual config files)

---

## 🗑️ Cleanup Commands

```powershell
# Navigate to workspace
cd "c:\Users\lucia\OneDrive\Desktop\control-3.2.9"

# Delete test scripts
Remove-Item analyze_dark_correction.py, benchmark_batch_processing.py, check_dark_noise.py, check_npz_contents.py, diagnostic_wavelength_ranges.py, flame_t_feature_discovery.py, led_timing_diagnostic.py, led_timing_diagnostic_batch.py, pico_batch_command_diagnostic.py, quick_batch_test.py, quick_dark_diagnostic.py, realtime_batch_monitor.py, scan_batch_performance_test.py, test_batch_led_control.py, test_first_scan_quality.py, test_hardware_detection.py, test_led_functionality.py, test_sequential_4led.py

# Delete test results
Remove-Item led_*.png, led_*.json, pico_*.json, benchmark_results -Recurse -Force

# Delete superseded documentation
Remove-Item BATCH_LED_CONTROL_*.md, BATCH_SCAN_PROCESSING_ANALYSIS.md, COMPLETE_OPTIMIZATION_WORKFLOW.md, CPU_SIDE_PROCESSING_OPTIMIZATIONS.md, DARK_LED_OFF_FIX.md, DARK_NOISE_FLOW_ANALYSIS.md, FIRST_SCAN_QUALITY_ANALYSIS.md, IMPLEMENTATION_TODO.md, INTEGRATION_TIME_*.md, LED_MINIMUM_INTENSITY_FIX.md, LED_TIMING_DIAGNOSTIC_BATCH_RESULTS.md, PHASE_*.md, P_MODE_*.md, S_MODE_REFERENCE_FLOW_ANALYSIS.md, CONFIGURATION_ANSWER.md, DEVICE_CONFIGURATION_QUICK_REF.md

# Delete unused utils
Remove-Item utils\adaptive_batch_processor.py, utils\optimized_batch_processor.py, utils\usb_spectrometer.py, utils\config_cli.py -ErrorAction SilentlyContinue
Remove-Item tests\test_optimized_batch_processor.py -ErrorAction SilentlyContinue
```

---

## 📦 Git Add & Commit

```powershell
# Add new device configuration system
git add widgets/device_settings.py
git add utils/hardware_detection.py
git add utils/device_configuration.py
git add utils/calibration_data_loader.py
git add factory_provision_device.py
git add install_config.py
git add setup_device.py

# Add essential documentation
git add DEVICE_DEPLOYMENT_GUIDE.md
git add DEPLOYMENT_QUICK_SUMMARY.md
git add CONFIG_QUICK_REFERENCE.md
git add HARDWARE_DETECTION_FIX.md
git add CALIBRATION_ACCELERATION_GUIDE.md
git add CALIBRATION_DATA_PERSISTENCE_COMPLETE.md
git add FRESH_CALIBRATION_GUARANTEE.md
git add TIMING_PARAMETERS_INTEGRATION_COMPLETE.md

# Add modified files
git add widgets/settings_menu.py

# Add config directory structure (with .gitignore)
git add config/.gitignore

# Commit all modified tracked files
git add -u

# Create commit
git commit -m "Add device configuration system with GUI and hardware detection

- NEW: Device Configuration GUI widget (widgets/device_settings.py)
  - Radio buttons for optical fiber diameter (100/200 µm)
  - LED PCB model selection
  - Hardware auto-detection via SeaBreeze and serial
  - Import/export config files

- NEW: Hardware detection (utils/hardware_detection.py)
  - SeaBreeze support for Ocean Optics spectrometers
  - Uses cseabreeze backend for reliable detection
  - Auto-detects Pico controller via serial port
  - Extracts serial numbers for device identification

- NEW: Device configuration management (utils/device_configuration.py)
  - JSON-based config storage on PC
  - Optical fiber diameter, LED model, timing parameters
  - Calibration file associations

- NEW: Factory provisioning script (factory_provision_device.py)
  - Auto-detect hardware during QC
  - Generate unique device IDs
  - Export config to USB drive for shipping

- NEW: Customer installation script (install_config.py)
  - USB-based config distribution
  - Automatic calibration file installation
  - 2-minute customer setup

- UPDATED: Settings menu (widgets/settings_menu.py)
  - Added Device Configuration tab

- DOCS: Complete deployment guide and quick references
  - Device deployment workflow
  - Hardware detection fix (SeaBreeze cseabreeze backend)
  - Calibration optimization strategies

This enables easy device configuration without manual file editing
and provides a complete factory-to-customer deployment workflow."

# Push to GitHub
git push origin master
```

---

## 📝 .gitignore Update

Create/update `.gitignore` in `config/` directory:

```
# Ignore actual device configuration files
device_config.json
device_config_*.json

# Ignore calibration data
*.npz
calibration/

# Keep directory structure
!.gitignore
```

---

## 🎯 After Cleanup

Workspace will contain:
- ✅ Clean production code
- ✅ Device configuration system
- ✅ Essential documentation only
- ✅ No test/diagnostic clutter
- ✅ Clear path for optimization work

Next Steps:
1. ✅ Cleanup complete
2. ✅ Pushed to GitHub
3. 🔄 Ready to integrate into main app
4. 🔄 Ready for optimization work

---

## Summary

**Delete**: 50+ test scripts, images, and superseded docs
**Add to Git**: 8 new files + 8 docs = 16 files
**Commit Message**: Device configuration system with GUI and hardware detection
**Result**: Clean workspace ready for main app integration

