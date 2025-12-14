# AffiLabs.core Beta - Documentation Index

**Last Updated:** November 23, 2025

## 📚 Main Documentation

### 🔥 **START HERE**
- **`START_HERE.md`** - Quick overview and important notes
- **`README_HARDWARE_BEHAVIOR.md`** - **COMPLETE hardware connection reference** ⭐

## 📁 Detailed Documentation (`docs/` folder)

### Hardware & Connection
- **`HARDWARE_CONNECTION_LOGIC_FIX.md`** - Device type identification fix details
- **`POWER_BUTTON_BEHAVIOR_FIX.md`** - Power button state machine fix details

### Device Configuration & Storage
- **`EEPROM_DEVICE_CONFIG_SPEC.md`** - **EEPROM portable backup specification** ⭐
- **`EEPROM_IMPLEMENTATION_SUMMARY.md`** - Implementation guide and status
- **`DEVICE_CONFIG_STATUS.md`** - Device config dialog implementation status
- **`CALIBRATION_SYSTEMS_SUMMARY.md`** - Afterglow and S/P orientation validation

### UI & Integration
- **`UI_ADAPTER_EXAMPLES.md`** - UI adapter usage examples
- **`UI_ADAPTER_REFERENCE.md`** - Complete UI adapter API reference

## 🔑 Key Concepts

### Power Button States
```
GRAY (disconnected) → Click → YELLOW (searching)
YELLOW (searching) → Click → GRAY (cancelled)
YELLOW (searching) → Hardware found → GREEN (connected)
GREEN (connected) → Click → Confirm → GRAY (disconnected)
```

### Scan Safety
⚠️ **Scanning hardware while already connected will NOT disconnect**
- Hardware manager checks if connections exist
- If connected → reports status and exits
- If not connected → performs USB scan

### Device Type Rules
- **Arduino OR PicoP4SPR alone** = P4SPR
- **PicoP4SPR + RPi controller** = P4SPR+KNX or ezSPR
- **PicoEZSPR** = P4PRO
- **Nothing found** = Empty string, power button returns to gray

## 📍 Where to Find Things

| What You Need | File |
|---------------|------|
| Hardware connection reference | `README_HARDWARE_BEHAVIOR.md` |
| Power button behavior | `README_HARDWARE_BEHAVIOR.md` or `docs/POWER_BUTTON_BEHAVIOR_FIX.md` |
| Device type identification | `README_HARDWARE_BEHAVIOR.md` or `docs/HARDWARE_CONNECTION_LOGIC_FIX.md` |
| **EEPROM device config backup** | **`EEPROM_DEVICE_CONFIG_SPEC.md`** ⭐ |
| **EEPROM implementation guide** | **`EEPROM_IMPLEMENTATION_SUMMARY.md`** |
| Device config dialog | `DEVICE_CONFIG_STATUS.md` |
| Calibration systems (afterglow, S/P) | `CALIBRATION_SYSTEMS_SUMMARY.md` |
| UI integration examples | `UI_ADAPTER_EXAMPLES.md` |
| Quick start guide | `START_HERE.md` |

## 🎯 Before You Code

**Making changes to:**
- Power button? → Read `README_HARDWARE_BEHAVIOR.md` first
- Hardware scanning? → Read `README_HARDWARE_BEHAVIOR.md` first
- Device detection? → Read `README_HARDWARE_BEHAVIOR.md` first
- **Device config storage?** → Read `EEPROM_DEVICE_CONFIG_SPEC.md` first
- **Adding EEPROM features?** → Check `EEPROM_IMPLEMENTATION_SUMMARY.md`
- Calibration systems? → Check `CALIBRATION_SYSTEMS_SUMMARY.md`
- UI updates? → Check `UI_ADAPTER_EXAMPLES.md`

## 🔧 Source Code Reference

### Core Files
- `affilabs_core_ui.py` - Main UI window and power button
- `main_simplified.py` - Application layer and signal handlers
- `core/hardware_manager.py` - Hardware detection and connection
- `utils/controller.py` - Controller implementations (includes EEPROM methods)
- `utils/device_configuration.py` - Device config with EEPROM fallback
- `ui_adapter.py` - UI abstraction layer

### UI Components
- `widgets/sidebar_modern.py` - Device Status widget
- `widgets/sections.py` - Graph control panels
- `widgets/plot_helpers.py` - Plot configuration

### Firmware
- `firmware/arduino_p4spr_with_eeprom_config.ino` - Arduino with EEPROM config support

## 💡 Tips

1. **Always check README_HARDWARE_BEHAVIOR.md before modifying connection logic**
2. **Document any changes you make in README_HARDWARE_BEHAVIOR.md**
3. **Test power button behavior after any hardware changes**
4. **Verify scan safety: connect hardware, then click scan - should NOT disconnect**
5. **EEPROM device config is portable - device works on any computer without JSON**
6. **Load priority: JSON → EEPROM → Defaults (graceful fallback)**
7. **Sync to EEPROM on major config changes (LED model, fiber, polarizer)**

## 🗂️ Configuration Storage Architecture

### Two-Tier Storage System
**EEPROM (Controller Flash Memory):**
- 20 bytes: Device config backup (LED model, fiber, polarizer, servos, intensities)
- Purpose: Portable backup that travels with hardware
- Benefits: Device works on any computer, survives JSON corruption

**JSON Files (`config/devices/{SERIAL}/`):**
- Full configuration with calibration history, maintenance tracking
- Primary storage during normal operation
- Auto-generated from EEPROM if missing

### Load Priority
```
1. JSON exists? → Load from JSON
2. No JSON but EEPROM valid? → Load from EEPROM, create JSON
3. Both missing? → Use defaults, prompt for config
```

### When EEPROM is Synced
- After calibration completion (auto)
- On major config changes: LED model, fiber diameter, polarizer type (auto)
- Manual "Push to EEPROM" button (optional UI feature)
- Factory pre-configuration (ships ready-to-use)

---

**Remember:** The goal is to NEVER repeat the same workflow or explanation.
All critical information is documented here. Read first, code second.
