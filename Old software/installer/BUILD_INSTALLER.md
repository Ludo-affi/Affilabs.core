# ezControl Installer Build Instructions

## Prerequisites

1. **Download and Install Inno Setup 6**
   - Download from: https://jrsoftware.org/isdl.php
   - Install the Unicode version (recommended)
   - Version 6.2 or later recommended

## Required Files

Before building the installer, you need to gather these files:

### 1. Application Files (Already Have)
- ✅ `dist\ezControl.exe` - Main application

### 2. Driver Files (Need to Download)

Create a `drivers` folder in the installer directory and add:

#### FTDI USB Drivers
- Download from: https://ftdichip.com/drivers/vcp-drivers/
- Get: `CDM212364_Setup.exe` (or latest version)
- Rename to: `FTDI_CDM_Driver.exe`
- Place in: `installer\drivers\`

#### LibUSB Drivers (if needed for spectrometer)
- Download from: https://github.com/libusb/libusb/releases
- Or use Zadig: https://zadig.akeo.ie/
- Place in: `installer\drivers\`

### 3. Visual C++ Redistributable (Optional but Recommended)

Download and place in `installer\redist\`:
- Download: https://aka.ms/vs/17/release/vc_redist.x64.exe
- Rename to: `VC_redist.x64.exe`

### 4. Optional Files

Create these files in the main directory:
- `LICENSE.txt` - Your license file
- `icon.ico` - Application icon (256x256 recommended)

## Folder Structure

```
Old software\
├── dist\
│   └── ezControl.exe
├── config\
│   └── devices\
├── installer\
│   ├── ezControl_Setup.iss         (Main installer script)
│   ├── drivers\
│   │   ├── FTDI_CDM_Driver.exe
│   │   └── libusb_driver_installer.exe (optional)
│   ├── redist\
│   │   └── VC_redist.x64.exe
│   └── output\                     (Created automatically)
├── LICENSE.txt                     (Create if needed)
├── icon.ico                        (Create if needed)
└── README.md
```

## Build Steps

### Option 1: Using Inno Setup GUI

1. Open Inno Setup Compiler
2. Click **File → Open**
3. Navigate to: `Old software\installer\ezControl_Setup.iss`
4. Click **Build → Compile** (or press F9)
5. Find the installer in: `installer\output\ezControl_Setup_4.0.exe`

### Option 2: Using Command Line

```powershell
cd "c:\Users\ludol\ezControl-AI\Old software\installer"
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" ezControl_Setup.iss
```

### Option 3: Using the Build Script (Automated)

Run the provided PowerShell script:
```powershell
.\build_installer.ps1
```

## What the Installer Does

1. **Checks system requirements** (64-bit Windows)
2. **Installs ezControl.exe** to Program Files
3. **Copies configuration files** to the installation directory
4. **Optionally installs USB drivers**:
   - FTDI VCP drivers for USB-to-Serial
   - LibUSB drivers for USB devices
5. **Installs Visual C++ Runtime** (if not present)
6. **Creates Start Menu shortcuts**
7. **Creates Desktop shortcut** (optional)
8. **Provides clean uninstaller**

## Testing the Installer

1. Build the installer
2. Copy `ezControl_Setup_4.0.exe` to a clean test machine
3. Run the installer
4. Test the application
5. Test the uninstaller

## Troubleshooting

### "File not found" errors during build
- Ensure all paths in the `.iss` file are correct
- Check that `ezControl.exe` exists in `dist\` folder
- Verify driver files are in `installer\drivers\`

### Drivers not installing
- Ensure driver installers support silent mode (`/S` parameter)
- Check that you have administrator privileges
- Test drivers separately before bundling

### Application won't start after install
- Missing Visual C++ Redistributable - install manually
- USB drivers not installed properly - reinstall drivers
- Check Windows Event Viewer for error details

## Customization

Edit `ezControl_Setup.iss` to customize:
- Company name (line 5)
- Version number (line 4)
- Installation directory
- File associations
- Registry entries
- Post-install actions

## Distribution

The final installer will be a single `.exe` file:
- **Size**: ~110-150 MB (with all drivers)
- **Distribution**: Can be shared via email, USB, or download
- **No additional files needed** - completely self-contained

## Notes

- The installer is **digitally signed** if you have a code signing certificate
- Users need **administrator rights** to install drivers
- The application can run without admin rights after installation
- Uninstaller automatically removes all installed files
