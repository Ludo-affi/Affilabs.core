# ezControl - Complete Installer Package

This package contains everything needed to create a professional Windows installer for ezControl.

## 📦 Quick Start (3 Steps)

### Step 1: Install Inno Setup
```powershell
# Download and install Inno Setup 6 from:
# https://jrsoftware.org/isdl.php
```

### Step 2: Download Drivers (5 minutes)
```powershell
cd installer\drivers
# Follow instructions in DOWNLOAD_DRIVERS.md
# Download FTDI driver and VC++ redistributable
```

### Step 3: Build Installer
```powershell
cd installer
.\build_installer.ps1
```

Done! Your installer will be in `installer\output\ezControl_Setup_4.0.exe`

---

## 📋 What's Included

```
installer\
├── ezControl_Setup.iss          # Main installer script
├── build_installer.ps1           # Automated build script
├── BUILD_INSTALLER.md            # Detailed instructions
├── drivers\
│   ├── DOWNLOAD_DRIVERS.md      # Driver download guide
│   ├── FTDI_CDM_Driver.exe      # [Download needed]
│   └── libusb_driver_installer.exe  # [Optional]
└── redist\
    └── VC_redist.x64.exe        # [Download needed]
```

---

## 🎯 Features

The installer will:
- ✅ Install ezControl to Program Files
- ✅ Install USB drivers (FTDI, LibUSB)
- ✅ Install Visual C++ Runtime
- ✅ Create Start Menu shortcuts
- ✅ Create Desktop shortcut (optional)
- ✅ Handle admin permissions automatically
- ✅ Provide clean uninstaller
- ✅ Check for existing installations

---

## 🔧 System Requirements

**Development Machine:**
- Windows 10/11 (64-bit)
- Python 3.12 with PyInstaller
- Inno Setup 6

**Target Machine:**
- Windows 10/11 (64-bit)
- No other requirements!

---

## 📖 Detailed Documentation

- `BUILD_INSTALLER.md` - Complete build instructions
- `drivers\DOWNLOAD_DRIVERS.md` - Driver download guide
- `ezControl_Setup.iss` - Installer script (customizable)

---

## 🚀 Distribution

The final installer is a **single executable** (~120-150 MB) that can be:
- Emailed
- Shared via USB drive
- Hosted on website
- Distributed via network share

No additional files needed - completely self-contained!

---

## 🛠️ Customization

Edit `ezControl_Setup.iss` to change:
- Company name
- Version number
- Installation path
- Shortcuts
- File associations
- Registry entries

---

## 🐛 Troubleshooting

### "Cannot find ezControl.exe"
Solution: Run PyInstaller first to create the executable

### "Inno Setup not found"
Solution: Download from https://jrsoftware.org/isdl.php

### "Driver installation failed"
Solution: Test drivers have `/S` silent install support

### Application won't start on target machine
Solution: Ensure VC++ redistributable is included in installer

---

## 📝 License

MIT License - See LICENSE.txt

---

## 🆘 Support

For build issues:
1. Check `BUILD_INSTALLER.md` for detailed instructions
2. Verify all required files are present
3. Test on a clean virtual machine before distributing

---

## 🔄 Version History

**v4.0** - Initial InnoSetup installer with driver support
