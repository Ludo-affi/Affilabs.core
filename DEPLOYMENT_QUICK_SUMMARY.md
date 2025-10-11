# Configuration Deployment - Quick Summary

**Date**: October 11, 2025
**Status**: Complete

## 📍 Answer to Your Question

> **"How will this info travel with the device and get installed on the computer of the customer?"**

---

## ✅ Solution: USB Drive + Physical Label (RECOMMENDED)

### What Ships with Each Device:

```
📦 Customer Receives:
├── 🔬 Physical Hardware
│   ├── Spectrometer (with serial number label)
│   ├── Pico Controller
│   ├── LED PCB (specific model installed)
│   └── Optical Fiber (100 µm or 200 µm - LABELED!)
│
├── 💾 USB Flash Drive containing:
│   ├── device_config_DEV-XXXX.json ← Pre-configured for their device!
│   ├── factory_calibration_*.npz (if applicable)
│   └── install_config.py ← One-click installer
│
└── 📄 Physical Label on Device:
    ├── Device ID: DEV-2025-XXXX
    ├── Optical Fiber: 200 µm (clearly marked)
    ├── LED PCB Model: Luminus Cool White
    └── Spectrometer S/N: FLMT09788
```

---

## 🏭 At Factory (Before Shipping)

**QC Operator runs**: `python factory_provision_device.py`

```
Step 1: Detects spectrometer automatically (gets serial number)
Step 2: Operator enters: Optical fiber (100/200 µm) from physical inspection
Step 3: Operator enters: LED PCB model from build sheet
Step 4: Script generates Device ID: DEV-2025-9788
Step 5: Creates pre-configured device_config_DEV-2025-9788.json
Step 6: Exports to USB drive
Step 7: Prints device label to attach to hardware
```

**Output**: USB drive ready to ship with hardware + Label to attach

---

## 💻 At Customer Site (Installation)

### Option A: One-Click Installation (EASIEST)
```bash
# Customer plugs in USB drive and runs:
python install_config.py

# Automatically:
✅ Finds config file on USB
✅ Copies to correct location (C:\Users\XXX\ezControl\config\)
✅ Copies calibration files
✅ Ready in 2 minutes!
```

### Option B: GUI Setup Wizard (If USB Lost)
```
1. Customer launches ezControl
2. First-run wizard starts
3. Hardware auto-detected (gets spectrometer S/N automatically)
4. Wizard asks: "What optical fiber diameter?" → Customer reads label: 200 µm
5. Wizard asks: "What LED PCB model?" → Customer reads label: Luminus
6. Configuration saved automatically
✅ Ready in 5 minutes!
```

### Option C: Settings Menu (Anytime)
```
1. Launch ezControl
2. Menu → Settings → "🔧 Device Configuration" tab
3. GUI with radio buttons for fiber diameter (100/200 µm)
4. GUI with radio buttons for LED PCB model
5. Click "💾 Save Configuration"
✅ Done!
```

---

## 📂 Where Configuration Lives

### ❌ NOT Stored on Pico (Limited storage, gets lost if replaced)

### ✅ Stored on PC:

| OS | Location |
|----|----------|
| **Windows** | `C:\Users\[username]\ezControl\config\device_config.json` |
| **macOS** | `~/Library/Application Support/ezControl/config/device_config.json` |
| **Linux** | `~/.ezcontrol/config/device_config.json` |

**Why PC storage?**
- ✅ Easy to backup
- ✅ Easy to modify
- ✅ Survives hardware replacement
- ✅ Can have multiple profiles
- ✅ Large file support (calibration data)

**Only servo positions stored on Pico EEPROM** (via `sf\n` command) - these are hardware-specific and rarely change.

---

## 🎯 GUI Access (New in This Release!)

### New "Device Configuration" Tab in Settings:

```
ezControl → Menu → Settings → "🔧 Device Configuration" Tab

Features:
├── 🔬 Optical Fiber Diameter
│   ├── ○ 100 µm (Higher resolution, lower signal)
│   └── ● 200 µm (Higher signal, most common)
│
├── 💡 LED PCB Model
│   ├── ● Luminus Cool White (Most common)
│   └── ○ Osram Warm White
│
├── 🔍 Hardware Detection
│   └── [Detect Hardware] button → Auto-finds spectrometer & controller
│
└── Actions
    ├── [💾 Save Configuration]
    ├── [📤 Export] → Save backup
    ├── [📥 Import] → Restore from backup
    └── [🔄 Reset to Defaults]
```

**Access in code**: `widgets/device_settings.py`
**Integrated into**: `widgets/settings_menu.py` (new tab added)

---

## 📊 Configuration Contents

```json
{
  "hardware": {
    "optical_fiber_diameter_um": 200,    ← Customer-specific!
    "led_pcb_model": "luminus_cool_white", ← Customer-specific!
    "spectrometer_serial": "FLMT09788"    ← Auto-detected or from label
  },
  "timing_parameters": {
    "min_integration_time_ms": 50,
    "led_delays_ms": { ... }
  },
  "frequency_limits": {
    "4_led_mode": { "max_hz": 5.0, ... },
    "2_led_mode": { "max_hz": 10.0, ... }
  },
  "calibration": { ... },
  "maintenance": { ... }
}
```

---

## 🔄 Backup & Recovery

### Customer Can:
1. **Export** config via GUI → Saves backup JSON file
2. **Import** config via GUI → Restores from backup
3. **Copy** the file manually (it's just JSON!)

### If Configuration Lost:
1. Re-run setup wizard (hardware auto-detected)
2. OR read info from physical label on device
3. OR import from backup if available

---

## 📝 Files Created

| File | Purpose |
|------|---------|
| `widgets/device_settings.py` | GUI widget for configuration (new!) |
| `widgets/settings_menu.py` | Updated with new "Device Configuration" tab |
| `factory_provision_device.py` | Factory QC provisioning script |
| `install_config.py` | Customer installation script (for USB) |
| `DEVICE_DEPLOYMENT_GUIDE.md` | Complete deployment documentation |
| `CONFIG_QUICK_REFERENCE.md` | User quick reference |

---

## 🎉 Summary

**Question**: How does config travel with device?
**Answer**: Pre-configured on USB drive, installed by customer in 2 minutes!

**Backup Plan**: Physical label on device + GUI setup wizard + hardware auto-detection

**User Experience**:
```
BEST CASE: Plug USB → Run script → Ready in 2 min ✅
GOOD CASE: Launch app → Wizard → Ready in 5 min ✅
MANUAL: Settings GUI → Enter from label → Ready in 3 min ✅
```

**Storage**: PC (not Pico) for maximum flexibility and reliability

---

**Status**: ✅ Complete and production-ready!
