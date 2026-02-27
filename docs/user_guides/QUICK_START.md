# Affilabs.core — Quick Start Guide

**Version 2.0.5** — Release
⏱️ **Setup Time**: 5 minutes
📊 **Target**: Get to first measurement in 5 minutes

---

## Before You Begin

Verify you have:

- [ ] **Windows 10/11** on your computer
- [ ] **Python 3.12+** installed (download from [python.org](https://www.python.org/downloads/))
- [ ] **Git** installed (for cloning the repository)
- [ ] **USB4000 spectrometer** with WinUSB drivers installed
- [ ] **PicoP4SPR V2.4+** controller (with serial drivers)
- [ ] **USB and serial cables** connected to computer

**Not sure about drivers?** See [README.md Hardware Support](README.md#hardware-support) for driver links.

---

## Step 1: Install (⏱️ 2 min)

### Clone Repository
```powershell
git clone https://github.com/yourusername/ezControl-AI.git
cd ezControl-AI
```

### Create Python 3.12 Virtual Environment
```powershell
py -3.12 -m venv .venv312
```

### Activate Environment
```powershell
.\.venv312\Scripts\Activate.ps1
```

✅ You should see `(.venv312)` at the start of your terminal line

### Install Dependencies
```powershell
pip install -r requirements.txt
```

✅ Installation completes without errors

---

## Step 2: Connect Hardware (⏱️ 1 min)

### Physical Connections

- [ ] **USB4000 spectrometer** → USB port on your computer
- [ ] **PicoP4SPR controller** → available COM port (serial cable)
- [ ] **Power cables** connected as needed

### Verify Connection

Open **Device Manager** (Windows key + pause/break, or `devmgmt.msc`):

- [ ] USB4000 appears in **Universal Serial Bus controllers**
- [ ] PicoP4SPR appears in **Ports (COM & LPT)** (e.g., COM3, COM4)
- [ ] No yellow warning icons ⚠️

---

## Step 3: Launch (⏱️ 30 sec)

```powershell
.\tools\powershell\run_app_312.ps1
```

✅ Application window opens
✅ Power button visible (gray/disconnected state)
✅ No Python version errors

---

## Step 4: First Calibration (⏱️ 2-15 min)

### Click Power Button

The gray power button in the window will search for hardware.

### Follow Calibration Wizard

1. System detects **USB4000** and **PicoP4SPR**
2. Configuration dialog appears (first time only)
3. **Calibration starts automatically**
4. Progress bar shows 8 steps (wait, do NOT close window)
5. Power button turns **green** when done ✅

**First time**: ~5-10 minutes (servo calibration + LED optimization)
**Next time**: ~30 seconds (loads saved configuration)

**Stuck?** See [CALIBRATION_MASTER.md](affilabs/docs/CALIBRATION_MASTER.md) for detailed steps.

---

## Step 5: Start Measuring

### Power Button is Now Green

Click the **green power button** again to connect.

### Click "Start" Button

Main window displays **live sensorgram** (4 channels: A, B, C, D)

✅ Real-time binding curves appear
✅ Data updates automatically

### Record Data (Optional)

Click **record button** to save measurements to disk.

---

## Quick Troubleshooting

| Problem | Solution |
|---------|----------|
| **USB4000 not detected** | Install WinUSB drivers: [Ocean Optics seabreeze](https://github.com/oceanoptics/seabreeze) |
| **Python version error** | Always use `run_app_312.ps1` (not `python main.py`) |
| **App won't launch** | Kill stale processes: `taskkill /F /IM python.exe` |
| **COM port error** | Check Device Manager → Ports (COM & LPT) for your controller |
| **Calibration fails** | See [CALIBRATION_MASTER.md troubleshooting](affilabs/docs/CALIBRATION_MASTER.md#troubleshooting) |

**Still stuck?** Check [README.md Troubleshooting](README.md#troubleshooting) or open an issue.

---

## Next Steps

### 📖 Learn More

- **Hardware issues?** → [README.md Hardware Support](README.md#hardware-support)
- **Calibration details?** → [CALIBRATION_MASTER.md](affilabs/docs/CALIBRATION_MASTER.md)
- **Advanced features?** → [docs/ directory](docs/)
- **Building an executable?** → [BUILD_INSTALLER.md](docs/BUILD_INSTALLER.md)
- **Full documentation?** → [README.md](README.md)

### 🔧 Common Next Tasks

1. **Adjust LED intensity** - Sidebar controls (toggle with sidebar button)
2. **Switch polarization** - S/P mode toggle in sidebar
3. **Export data** - Click export after recording
4. **Set up pumps** - See [docs/](docs/) for fluid handling

---

## Key Commands Reference

```powershell
# Launch application (do this every time)
.\tools\powershell\run_app_312.ps1

# Kill stale Python processes (if app won't start)
taskkill /F /IM python.exe

# Stop the app
# Press Ctrl+C in terminal, or close window and wait 10 seconds

# Remove virtual environment (to start fresh)
rmdir .venv312 /s /q
```

---

**⚡ Tip**: Save this file for quick reference. You only need to read it once!

**Questions?** Check [README.md](README.md) or [DOCUMENTATION_INDEX.md](affilabs/docs/DOCUMENTATION_INDEX.md) for comprehensive guides.
