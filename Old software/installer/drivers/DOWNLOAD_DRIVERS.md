# Download USB Drivers

## FTDI VCP Drivers (Required)

The FTDI Virtual COM Port (VCP) drivers are needed for USB-to-Serial communication.

### Download Steps:

1. **Visit FTDI Website**:
   - Go to: https://ftdichip.com/drivers/vcp-drivers/

2. **Download Windows Drivers**:
   - Click on "Windows" section
   - Download the latest "setup executable" for Windows (x64)
   - Current version: CDM212364_Setup.exe or similar

3. **Save to This Folder**:
   - Rename the downloaded file to: `FTDI_CDM_Driver.exe`
   - Place it in: `installer\drivers\FTDI_CDM_Driver.exe`

### Direct Download Link:
https://ftdichip.com/wp-content/uploads/2024/08/CDM212364_Setup.exe

---

## LibUSB Drivers (Optional - for Spectrometers)

If your hardware uses generic USB devices (like Ocean Optics spectrometers):

### Option 1: Zadig (Recommended for end-users)

1. **Download Zadig**:
   - Visit: https://zadig.akeo.ie/
   - Download latest version: zadig-2.8.exe

2. **Save to This Folder**:
   - Rename to: `libusb_driver_installer.exe`
   - Place in: `installer\drivers\libusb_driver_installer.exe`

### Option 2: libusb-win32

1. **Visit**: https://sourceforge.net/projects/libusb-win32/
2. **Download**: libusb-win32-bin-X.X.X.X.zip
3. **Extract** and place installer in drivers folder

---

## Visual C++ Redistributable (Recommended)

Python applications may need the Visual C++ Runtime.

### Download Steps:

1. **Visit Microsoft**:
   - Go to: https://aka.ms/vs/17/release/vc_redist.x64.exe
   - This downloads automatically (14 MB)

2. **Save to This Folder**:
   - Place file in: `installer\redist\VC_redist.x64.exe`

### Direct Link:
https://aka.ms/vs/17/release/vc_redist.x64.exe

---

## Folder Structure After Download

```
installer\
├── drivers\
│   ├── FTDI_CDM_Driver.exe           ← Download this
│   └── libusb_driver_installer.exe   ← Optional
├── redist\
│   └── VC_redist.x64.exe             ← Download this
└── (installer scripts)
```

---

## Verification

After downloading, you should have:
- ✅ `drivers\FTDI_CDM_Driver.exe` (Required)
- ✅ `redist\VC_redist.x64.exe` (Recommended)
- ⚪ `drivers\libusb_driver_installer.exe` (Optional)

---

## Alternative: Skip Drivers

If you want to create a basic installer without drivers:

1. Edit `ezControl_Setup.iss`
2. Comment out or remove the `[Tasks]` driver installation option
3. Build the installer normally

Users will need to install drivers manually if hardware doesn't work.
