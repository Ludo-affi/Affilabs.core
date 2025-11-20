# Quick Build Guide - Upgrade Installation

Since the target computer already has ezControl and drivers installed, you can create a **lightweight upgrade installer** that skips the driver installation.

## ⚡ Fast Track (10 Minutes Total)

### Step 1: Install Inno Setup (5 min - One Time Only)
```
Download: https://jrsoftware.org/isdl.php
Install the Unicode version
```

### Step 2: Build the Installer (1 min)
```powershell
cd "c:\Users\ludol\ezControl-AI\Old software\installer"
.\build_installer.ps1 -SkipDriverCheck
```

**That's it!** The installer will be in `installer\output\ezControl_Setup_4.0.exe`

---

## 📦 What Gets Installed

Since drivers are already on the target computer, the installer will only:
- ✅ Update ezControl.exe to the new version
- ✅ Preserve existing configuration files
- ✅ Update Start Menu shortcuts
- ✅ Skip driver installation (unchecked by default)

**Result**: A lean ~105 MB installer (vs ~150 MB with drivers)

---

## 🎯 Installation on Target Computer

1. **Run** `ezControl_Setup_4.0.exe` on the target computer
2. **Install Location**: Use the same location as the old version (or new location)
3. **Driver Options**: Leave "Install USB drivers" **UNCHECKED** (already installed)
4. **Desktop Shortcut**: Optional
5. **Click Install**

The new version will replace the old one. All settings and drivers remain intact.

---

## 💡 Even Simpler: Direct Copy Method

Since drivers are already installed, you could also just:

1. **Stop** the old ezControl if running
2. **Replace** the old `ezControl.exe` with the new one
3. **Done!**

But the installer is safer because it:
- Handles file permissions correctly
- Updates shortcuts
- Provides uninstaller
- Checks for conflicts

---

## 🔄 Upgrade vs Fresh Install

**Upgrade Mode** (Recommended):
- Drivers already present ✅
- Faster installation ✅  
- Preserves settings ✅
- Just update the app ✅

**Fresh Install Mode**:
- Need all drivers ❌
- Longer download ❌
- More complex ❌

---

## 📝 What You Don't Need

Since drivers exist on target computer, you can **skip downloading**:
- ❌ FTDI drivers
- ❌ LibUSB drivers  
- ❌ VC++ redistributable (probably already there too)

**Just build and go!**

---

## 🚀 Summary

For upgrading a computer that already has ezControl:

1. Install Inno Setup (one-time)
2. Run `.\build_installer.ps1 -SkipDriverCheck`
3. Copy `ezControl_Setup_4.0.exe` to target computer
4. Run installer, uncheck drivers, install
5. Done!

**Total time: ~10 minutes** (most of it is Inno Setup download)
