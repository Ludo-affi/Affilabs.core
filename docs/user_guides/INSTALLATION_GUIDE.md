# Affilabs.core v2.0.5 — Installation Guide

**Last Updated:** February 24, 2026  
**Audience:** End users installing Affilabs.core from the provided installer

---

## System Requirements

| Requirement | Minimum | Recommended |
|------------|---------|-------------|
| **Operating System** | Windows 10 (build 19041+), 64-bit | Windows 11, 64-bit |
| **RAM** | 8 GB | 16 GB |
| **Disk Space** | 2 GB free | 5 GB free (for data storage) |
| **USB Ports** | 1× USB 2.0 (spectrometer) + 1× USB/serial (controller) | USB 3.0 |
| **Display** | 1366 × 768 | 1920 × 1080 or higher |
| **Internet** | Not required for operation | Required for updates |

> **Note:** macOS and Linux are **not supported**. Affilabs.core is Windows-only.

---

## Step 1: Run the Installer

1. Double-click the provided installer file: **`Affilabs-Core-Setup-2.0.5.exe`**
2. Follow the on-screen prompts:
   - Accept the license agreement
   - Choose installation directory (default: `C:\Program Files\Affilabs-Core\`)
   - Click **Install**
3. Wait for the installation to complete — this takes approximately 1–2 minutes

The installer includes:
- Affilabs.core application
- Zadig USB driver utility (bundled)

---

## Step 2: Install the Spectrometer USB Driver

Your spectrometer (Flame-T or USB4000) requires the **WinUSB** driver to communicate with the software.

### First-Time Setup (Zadig)

1. **Connect your spectrometer** to the computer via USB
2. **Open Zadig** — it was installed alongside Affilabs.core, or find it in the installation directory
3. In Zadig:
   - Select your device from the dropdown:
     - Flame-T appears as: **`USB4000`** or **`Ocean Optics USB4000`**
     - If not listed, check **Options → List All Devices**
   - Set the target driver to **WinUSB**
   - Click **Replace Driver** (or **Install WCID Driver** if shown)
4. Wait for the confirmation message: **"Driver installed successfully"**
5. **Close Zadig**

> **Important:** You only need to do this once per computer. The driver persists across reboots and software updates.

### Verifying the Driver

After installing the driver:
1. Open **Device Manager** (Win + X → Device Manager)
2. Look under **Universal Serial Bus devices**
3. You should see your spectrometer listed (not under "Unknown devices")

If the device shows under "Unknown devices" with a yellow warning icon, repeat the Zadig process.

---

## Step 3: Connect the Controller

The PicoP4SPR (or P4PRO) controller connects via a USB serial connection.

1. **Connect the controller** to the computer via USB cable
2. Windows should automatically install the serial driver (FTDI / CH340)
3. If prompted, allow Windows to install the driver automatically
4. No additional driver installation is needed for the controller

### Verifying the Controller Connection

1. Open **Device Manager**
2. Under **Ports (COM & LPT)**, you should see a new COM port (e.g., `COM3`)
3. Note the COM port number — the software will auto-detect it

---

## Step 4: First Launch

1. **Launch Affilabs.core** from the Start Menu or Desktop shortcut
2. The splash screen will appear for a few seconds while the application loads
3. On first launch:
   - The application will scan for connected hardware automatically
   - If your spectrometer and controller are connected, they will appear in the sidebar **Hardware Status** section
   - If no hardware is detected, check your USB connections and drivers (Steps 2–3)

### Hardware Detection

The sidebar shows three hardware subunits:

| Subunit | What it means |
|---------|--------------|
| **Spectrometer** ● Green | Flame-T or USB4000 detected and communicating |
| **Controller** ● Green | PicoP4SPR/P4PRO firmware responding |
| **Pump** ● Grey | AffiPump not connected (normal for P4SPR) |

Once both Spectrometer and Controller show green, you're ready to calibrate.

---

## Step 5: Run Calibration

Before your first measurement, the system must calibrate:

1. Ensure a **sensor chip is installed** in the instrument and **water/buffer** covers the sensor surface
2. Click **Calibrate** in the sidebar
3. The calibration process takes 30–90 seconds and includes:
   - Servo position detection (S-pol and P-pol)
   - LED intensity convergence
   - S-polarization reference capture
4. When calibration is complete, the sensorgram will begin displaying live data

> **Tip:** See the [Calibration Guide](../calibration/CALIBRATION_GUIDE.md) for detailed calibration information and troubleshooting.

---

## Troubleshooting Installation

### Spectrometer not detected

| Symptom | Solution |
|---------|----------|
| Device shows in Device Manager with yellow icon | Re-run Zadig (Step 2) |
| Device not listed in Zadig | Try a different USB port; check cable |
| "Access denied" error in software | Close any other software that might be using the spectrometer (OceanView, SpectraSuite) |
| Multiple "Unknown" USB devices | This is normal (phantom devices). The software uses a handshake test to find the real one — ignore phantom entries. |

### Controller not detected

| Symptom | Solution |
|---------|----------|
| No COM port in Device Manager | Try a different USB cable (data-capable, not charge-only) |
| COM port appears but software doesn't connect | Check that no other serial terminal (PuTTY, etc.) has the port open |
| "Firmware version unsupported" | Update controller firmware to V2.4 (contact Affinite Instruments) |

### Application won't start

| Symptom | Solution |
|---------|----------|
| Application closes immediately | Run from command line to see error: `Affilabs-Core.exe` from the install directory |
| "Python version" error | The bundled executable includes Python — this should not occur. Contact support. |
| Antivirus blocks the application | Add Affilabs.core to your antivirus whitelist / exclusion list |

---

## Uninstalling

1. Open **Settings → Apps & features** (or **Add/Remove Programs**)
2. Find **Affilabs-Core** in the list
3. Click **Uninstall**
4. Follow the prompts

> **Note:** Uninstalling does not remove your experiment data. Data files are stored in your user directory and can be manually deleted if desired.

---

## Support

If you need help with installation:

- **Email:** info@affiniteinstruments.com
- **Include:** Your Windows version, spectrometer model, and any error messages

---

**© 2026 Affinite Instruments Inc.**
