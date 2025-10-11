# Device Configuration Deployment Guide

**Version**: 1.0
**Date**: October 11, 2025

## Overview

This document describes how device configuration travels with the hardware and gets installed on customer computers.

---

## 🎯 Deployment Strategy

### Current Architecture: **Hybrid Model** (RECOMMENDED)

```
┌─────────────────────────────────────────────────────────────┐
│                    CUSTOMER RECEIVES                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  📦 Physical Hardware                                        │
│  ├── Ocean Optics Spectrometer (with S/N label)            │
│  ├── Raspberry Pi Pico Controller (with firmware)          │
│  ├── LED PCB (specific model installed)                    │
│  └── Optical Fiber Probe (100 µm or 200 µm - LABELED!)     │
│                                                              │
│  💾 USB Flash Drive / QR Code                               │
│  ├── Pre-configured device_config.json                     │
│  ├── Factory calibration files (.npz)                      │
│  └── Setup instructions (PDF)                               │
│                                                              │
│  📄 Physical Label on Device                                │
│  ├── QR Code → links to configuration file                 │
│  ├── Device ID: DEV-2025-XXXX                              │
│  ├── Optical Fiber: 200 µm (or 100 µm)                     │
│  ├── LED PCB: Luminus Cool White                           │
│  └── Spectrometer S/N: FLMT09788                           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 📋 Three Deployment Methods

### Method 1: Pre-Configured USB Drive (RECOMMENDED)

**What Customer Receives:**
1. **Hardware** with physical labels
2. **USB Drive** containing:
   - `device_config_[SERIAL].json` - Pre-configured for their specific hardware
   - `factory_calibration_[SERIAL].npz` - Factory calibration data
   - `README.txt` - Simple setup instructions
   - `install_config.bat` - One-click installer script

**Customer Setup Process:**
```bash
# Customer plugs in USB drive and runs:
install_config.bat

# This script:
# 1. Copies device_config.json to correct location
# 2. Copies calibration files
# 3. Installs ezControl software (if needed)
# 4. Runs hardware verification
# 5. Opens the application
```

**Benefits:**
- ✅ No manual configuration needed
- ✅ Factory calibration included
- ✅ Foolproof installation
- ✅ Works offline

---

### Method 2: QR Code + Cloud Retrieval

**What Customer Receives:**
1. **Hardware** with QR code label on device
2. **Quick Start Card** with QR code

**Customer Setup Process:**
```
1. Install ezControl software
2. Launch application
3. Click "Scan Device QR Code" button
4. Point camera at QR code on device
5. Software downloads configuration from cloud
6. Automatic setup complete!
```

**QR Code Contains:**
```
https://affinite.com/device/DEV-2025-1234
  ↓
JSON Response:
{
  "device_id": "DEV-2025-1234",
  "optical_fiber_um": 200,
  "led_pcb_model": "luminus_cool_white",
  "spectrometer_serial": "FLMT09788",
  "factory_calibration_url": "https://...",
  "manufacturing_date": "2025-10-11"
}
```

**Benefits:**
- ✅ Modern, user-friendly
- ✅ No USB drive needed
- ✅ Easy to update configuration remotely
- ✅ Tracking and analytics possible

**Requirements:**
- ❌ Requires internet connection
- ❌ Need to maintain cloud server

---

### Method 3: Smart First-Run Setup Wizard

**What Customer Receives:**
1. **Hardware** with physical labels showing specs
2. **Software** with intelligent setup wizard

**Customer Setup Process:**
```
1. Install ezControl software
2. Launch application (first time)
3. Wizard automatically:
   - Detects connected hardware (spectrometer, controller)
   - Reads serial numbers
   - Asks customer to enter info from label:
     • Optical Fiber: 100 µm or 200 µm? [___]
     • LED PCB Model: [dropdown]
   - Saves configuration
   - Downloads factory calibration (if available)
4. Setup complete!
```

**Benefits:**
- ✅ No physical media needed
- ✅ Hardware auto-detection validates setup
- ✅ Customer involvement minimal
- ✅ Works offline after initial setup

---

## 🏭 Manufacturing/QC Process

### At Factory (Before Shipping)

```python
# Factory QC Station Script
# ========================

from utils.device_configuration import DeviceConfiguration
from utils.hardware_detection import HardwareDetector
import json
from datetime import datetime

def factory_provision_device():
    """Run at QC station before shipping."""

    print("=" * 60)
    print("AFFINITÉ FACTORY PROVISIONING")
    print("=" * 60)

    # Step 1: Detect hardware
    detector = HardwareDetector()
    detected = detector.detect_all_hardware()

    if not detected['spectrometer']:
        print("❌ ERROR: Spectrometer not detected!")
        return False

    # Step 2: QC operator enters physical configuration
    print("\nEnter device configuration:")

    optical_fiber = input("Optical Fiber (100/200): ").strip()
    if optical_fiber not in ['100', '200']:
        print("❌ Invalid fiber diameter")
        return False

    led_model = input("LED PCB Model (1=Luminus, 2=Osram): ").strip()
    led_model_map = {'1': 'luminus_cool_white', '2': 'osram_warm_white'}
    led_pcb_model = led_model_map.get(led_model)

    if not led_pcb_model:
        print("❌ Invalid LED model")
        return False

    # Step 3: Generate device ID
    device_id = f"DEV-{datetime.now().strftime('%Y')}-{detected['spectrometer']['serial_number'][-4:]}"

    # Step 4: Create configuration
    config = DeviceConfiguration()
    config.set_optical_fiber_diameter(int(optical_fiber))
    config.set_led_pcb_model(led_pcb_model)
    config.set_spectrometer_serial(detected['spectrometer']['serial_number'])
    config.config['device_info']['device_id'] = device_id

    # Step 5: Export to USB drive
    usb_path = "E:\\"  # USB drive
    export_file = f"{usb_path}device_config_{device_id}.json"
    config.export_config(export_file)

    # Step 6: Generate QR code (optional)
    qr_url = f"https://affinite.com/device/{device_id}"
    print(f"\n✅ Device provisioned: {device_id}")
    print(f"📄 Config exported to: {export_file}")
    print(f"🔗 QR Code URL: {qr_url}")
    print(f"\n📋 PRINT LABEL:")
    print(f"   Device ID: {device_id}")
    print(f"   Fiber: {optical_fiber} µm")
    print(f"   LED: {led_pcb_model.replace('_', ' ').title()}")
    print(f"   Spec S/N: {detected['spectrometer']['serial_number']}")

    return True

if __name__ == "__main__":
    factory_provision_device()
```

---

## 💻 Customer Installation Scripts

### Windows: `install_config.bat`

```batch
@echo off
REM Affinité ezControl Configuration Installer
REM Automatically installs device configuration

echo ================================================
echo Affinite ezControl - Configuration Installer
echo ================================================
echo.

REM Check if running from USB drive
if not exist device_config_*.json (
    echo ERROR: Configuration file not found!
    echo Please run this script from the USB drive.
    pause
    exit /b 1
)

REM Find configuration file
for %%f in (device_config_*.json) do set CONFIG_FILE=%%f

echo Found configuration: %CONFIG_FILE%
echo.

REM Create config directory
set CONFIG_DIR=%USERPROFILE%\ezControl\config
if not exist "%CONFIG_DIR%" (
    echo Creating configuration directory...
    mkdir "%CONFIG_DIR%"
)

REM Copy configuration
echo Installing device configuration...
copy "%CONFIG_FILE%" "%CONFIG_DIR%\device_config.json"

REM Copy calibration files (if present)
if exist factory_calibration_*.npz (
    echo Installing factory calibration...
    copy factory_calibration_*.npz "%CONFIG_DIR%\"
)

echo.
echo ================================================
echo Installation Complete!
echo ================================================
echo.
echo Configuration installed to:
echo %CONFIG_DIR%
echo.
echo You can now launch ezControl.
echo.
pause
```

### Python: `install_config.py` (Cross-platform)

```python
#!/usr/bin/env python3
"""
Affinité ezControl Configuration Installer
Automatically installs device configuration from USB drive.
"""

import os
import shutil
import sys
from pathlib import Path
import glob

def find_config_file():
    """Find device configuration file on current drive."""
    # Look for device_config_*.json
    configs = glob.glob("device_config_*.json")
    if configs:
        return Path(configs[0])
    return None

def install_configuration():
    """Install device configuration."""
    print("=" * 60)
    print("Affinité ezControl - Configuration Installer")
    print("=" * 60)
    print()

    # Find configuration file
    config_file = find_config_file()
    if not config_file:
        print("❌ ERROR: Configuration file not found!")
        print("   Please run this script from the USB drive.")
        input("Press Enter to exit...")
        return False

    print(f"✅ Found configuration: {config_file.name}")
    print()

    # Determine installation directory
    if sys.platform == "win32":
        config_dir = Path.home() / "ezControl" / "config"
    else:
        config_dir = Path.home() / ".ezcontrol" / "config"

    # Create directory if needed
    config_dir.mkdir(parents=True, exist_ok=True)

    # Install configuration
    dest_file = config_dir / "device_config.json"
    print(f"Installing to: {dest_file}")
    shutil.copy2(config_file, dest_file)
    print("✅ Configuration installed")
    print()

    # Install calibration files (if present)
    calib_files = glob.glob("factory_calibration_*.npz")
    if calib_files:
        print(f"✅ Found {len(calib_files)} calibration file(s)")
        for calib_file in calib_files:
            dest = config_dir / Path(calib_file).name
            shutil.copy2(calib_file, dest)
            print(f"   Installed: {Path(calib_file).name}")
        print()

    print("=" * 60)
    print("Installation Complete!")
    print("=" * 60)
    print()
    print("Configuration installed to:")
    print(f"  {config_dir}")
    print()
    print("You can now launch ezControl.")
    print()
    input("Press Enter to exit...")
    return True

if __name__ == "__main__":
    try:
        install_configuration()
    except Exception as e:
        print(f"\n❌ Installation failed: {e}")
        input("Press Enter to exit...")
        sys.exit(1)
```

---

## 📱 QR Code Integration (Future Enhancement)

### Add QR Scanner to Setup Wizard

```python
# In setup_device.py or GUI

def scan_device_qr():
    """Scan device QR code to download configuration."""
    try:
        import cv2  # OpenCV for camera access
        import requests
        from pyzbar import pyzbar  # QR code decoding

        print("📷 Point camera at device QR code...")

        cap = cv2.VideoCapture(0)

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Decode QR codes
            barcodes = pyzbar.decode(frame)

            for barcode in barcodes:
                barcode_data = barcode.data.decode("utf-8")

                if "affinite.com/device/" in barcode_data:
                    # Download configuration
                    response = requests.get(barcode_data)
                    device_config = response.json()

                    # Install configuration
                    config = DeviceConfiguration()
                    config.set_optical_fiber_diameter(device_config['optical_fiber_um'])
                    config.set_led_pcb_model(device_config['led_pcb_model'])
                    config.set_spectrometer_serial(device_config['spectrometer_serial'])
                    config.save()

                    print("✅ Configuration downloaded and installed!")
                    cap.release()
                    return True

            # Display frame
            cv2.imshow("Scan Device QR Code", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()
        return False

    except Exception as e:
        print(f"❌ QR scan failed: {e}")
        return False
```

---

## 🏷️ Physical Device Label Template

```
┌──────────────────────────────────────────────┐
│  AFFINITÉ SPR SYSTEM                         │
│  ┌─────────┐                                 │
│  │  [QR]   │  Device ID: DEV-2025-9788       │
│  │  CODE   │  Serial: FLMT09788              │
│  └─────────┘                                 │
│                                              │
│  CONFIGURATION:                              │
│  • Optical Fiber: 200 µm                    │
│  • LED PCB: Luminus Cool White              │
│  • Controller: Pi Pico P4SPR               │
│                                              │
│  Manufacturing Date: 2025-10-11              │
│  QC Approved: [Initials]                     │
│                                              │
│  🔗 Setup: affinite.com/setup               │
└──────────────────────────────────────────────┘
```

---

## 📝 Recommended Deployment Process

### **RECOMMENDED: Hybrid Approach**

1. **Physical Label** on device (always)
   - Shows optical fiber diameter
   - Shows LED PCB model
   - QR code for easy retrieval

2. **USB Drive** included with device (backup)
   - Pre-configured `device_config.json`
   - Factory calibration files
   - One-click installer script

3. **Software Wizard** (fallback)
   - Auto-detects hardware
   - Prompts for info from label if needed
   - Downloads calibration from cloud (if available)

### Customer Experience:

```
BEST CASE (USB Drive):
1. Plug in USB drive
2. Run install_config.bat
3. Launch ezControl
   ✅ Ready in 2 minutes

GOOD CASE (QR Code):
1. Launch ezControl
2. Click "Scan Device QR"
3. Point at QR code
   ✅ Ready in 3 minutes

FALLBACK CASE (Manual):
1. Launch ezControl
2. First-run wizard starts
3. Hardware auto-detected
4. Enter fiber diameter from label
5. Select LED model from label
   ✅ Ready in 5 minutes
```

---

## 🔄 Configuration Updates

### Remote Configuration Updates (If Needed)

```python
def check_for_config_updates():
    """Check if device configuration needs updating."""
    config = DeviceConfiguration()
    device_id = config.config['device_info'].get('device_id')

    if not device_id:
        return  # No device ID, skip check

    try:
        # Check with server
        response = requests.get(
            f"https://affinite.com/api/device/{device_id}/config-version",
            timeout=5
        )

        server_version = response.json()['config_version']
        local_version = config.config['device_info']['config_version']

        if server_version > local_version:
            # Prompt user to update
            reply = QMessageBox.question(
                None,
                "Configuration Update Available",
                f"A configuration update is available for your device.\n\n"
                f"Current version: {local_version}\n"
                f"New version: {server_version}\n\n"
                f"Would you like to update now?",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                download_and_install_config_update(device_id)

    except Exception as e:
        logger.debug(f"Config update check failed: {e}")
        # Silent failure - not critical
```

---

## 📊 Summary: Storage Locations

| Data Type | Stored Where | Why |
|-----------|-------------|-----|
| **Optical Fiber Diameter** | PC (device_config.json) | Experiment-specific, easy to modify |
| **LED PCB Model** | PC (device_config.json) | Hardware-specific, rarely changes |
| **Spectrometer Serial** | PC (device_config.json) | Detected automatically or from label |
| **Timing Parameters** | PC (device_config.json) | Calculated from hardware config |
| **Calibration Data** | PC (.npz files) | Large files, experiment-specific |
| **Servo Positions** | Pico EEPROM | Hardware-specific, rarely changes |
| **Firmware** | Pico Flash | Hardware control logic |

**Why not store everything on Pico?**
- ❌ Limited storage (2MB flash)
- ❌ Harder to modify/update
- ❌ Lost if Pico replaced
- ❌ No backup/versioning
- ❌ Requires serial communication
- ✅ PC storage is better for configuration

---

## 🎯 Action Items

### Immediate (For Current Deployment):
1. ✅ Create `install_config.py` script
2. ✅ Update `setup_device.py` to support USB config import
3. ✅ Create physical label template
4. ✅ Document QC/provisioning process

### Short-term (Next Release):
1. Add QR code generation to factory script
2. Create cloud API for configuration retrieval
3. Add QR scanner to GUI
4. Implement automatic config update checks

### Long-term (Future):
1. Mobile app for QR scanning
2. Cloud dashboard for device fleet management
3. Remote configuration management
4. Automated firmware updates

---

**RECOMMENDATION**: Start with **Method 1 (USB Drive)** for reliability, add **Method 2 (QR Code)** as enhancement later.

