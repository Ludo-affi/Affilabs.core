# SPR Application Troubleshooting Session - Oct 20, 2025

**Status**: Application running but calibration failing due to polarizer position mismatch

---

## 🔴 CRITICAL ISSUE: Polarizer Positions Swapped/Incorrect

### **Error Details**:

```
❌ POLARIZER POSITION ERROR DETECTED
   S-mode intensity (62169.3) is NOT significantly higher than P-mode (39358.8)
   Measured ratio: 1.58x (expected: >2.0x)
   OEM positions: S=165, P=50 (0-255 scale)
   Expected ratio: 15.89x (from OEM calibration)

⚠️ Hardware mismatch: Expected S=165 P=50, got S=30 P=120
   Re-applying positions to hardware...
```

### **Analysis**:

1. **Config says**: S=165 should give **15.89× more light** than P=50
2. **Actual measurement**: S gives only **1.58× more light** than P
3. **Hardware reports**: Servo is at S=30, P=120 (different from config!)
4. **Root cause**: Positions are likely **SWAPPED** or hardware changed since calibration

---

## ✅ GOOD NEWS

### **What's Working**:
- ✅ Hardware connected: PicoP4SPR + USB4000
- ✅ Calibrator created successfully
- ✅ Spectrum acquisitions working (detector reads OK)
- ✅ Application starts without crashes
- ✅ Code is functional (no syntax errors)

### **What's Broken**:
- ❌ Polarizer S/P positions incorrect
- ❌ Calibration cannot proceed until positions fixed
- ⚠️ COM4 permission error (port already in use - minor issue)

---

## 🔧 SOLUTION OPTIONS

### **Option 1: Quick Swap Test** (FASTEST - Try This First!)

The positions might just be swapped. Let's test by reversing them:

**Current config** (`config/device_config.json`):
```json
{
  "oem_calibration": {
    "polarizer_s_position": 165,
    "polarizer_p_position": 50
  }
}
```

**Try swapping**:
```json
{
  "oem_calibration": {
    "polarizer_s_position": 50,
    "polarizer_p_position": 165
  }
}
```

**Steps**:
1. Close the application (Ctrl+C or close window)
2. Edit `config/device_config.json`
3. Swap the S and P positions
4. Restart the application
5. See if S/P ratio improves

---

### **Option 2: Use Hardware's Current Positions** (QUICK FIX)

The log shows hardware is currently at: **S=30, P=120**

Try using these positions in config:

```json
{
  "oem_calibration": {
    "polarizer_s_position": 30,
    "polarizer_p_position": 120
  }
}
```

**Logic**: If hardware is already at S=30, P=120 and application can't move it, use those positions.

---

### **Option 3: Run Auto-Polarization** (BEST LONG-TERM)

Use the GUI to automatically find correct positions:

**Steps**:
1. Let the application load (even with error)
2. Go to: **Settings → Auto-Polarization**
3. Click "Run Auto-Polarization"
4. Tool will:
   - Sweep servo through all positions (10-255)
   - Find actual optimal S and P positions
   - Measure actual S/P ratio
   - **Automatically update `config/device_config.json`**
5. Restart application

---

### **Option 4: Run OEM Calibration Tool** (MANUFACTURING-LEVEL)

If GUI doesn't work, use command-line tool:

```powershell
# Kill application first
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force

# Run OEM calibration tool
python utils/oem_calibration_tool.py --serial FLMT09788 --skip-afterglow

# This will:
# - Find optimal S and P positions
# - Update config/device_config.json automatically
# - Take about 2-3 minutes
```

---

## ⚠️ MINOR ISSUE: COM4 Permission Error

```
Direct serial LED shutdown failed: could not open port 'COM4':
PermissionError(13, 'Access is denied.', None, 5)
```

**What this means**:
- COM4 is already in use by the main application
- Emergency shutdown tries to open it again → Permission denied
- This is **expected behavior** and not a real problem
- LEDs are already controlled by main connection

**How to fix** (if it bothers you):
- Just ignore it - it's a harmless warning
- Or: Unplug/replug USB cable to fully release port

---

## 📊 DIAGNOSTIC DATA

### **Current Configuration**:
```
Device: FLMT09788 (Flame-T spectrometer)
Controller: PicoP4SPR
S-position (config): 165
P-position (config): 50
Expected S/P ratio: 15.89x
```

### **Actual Measurements**:
```
S-mode intensity: 62,169 counts
P-mode intensity: 39,359 counts
Measured ratio: 1.58x
Hardware positions: S=30, P=120
```

### **Problem**:
- Config expects 15.89× ratio
- Actual measurement is 1.58×
- **This is 10× lower than expected!**
- Clear sign of swapped/incorrect positions

---

## 🎯 RECOMMENDED ACTION PLAN

### **Step 1: Try Quick Swap** (30 seconds)
1. Close application
2. Edit `config/device_config.json`
3. Change:
   ```json
   "polarizer_s_position": 50,   # Was 165
   "polarizer_p_position": 165   # Was 50
   ```
4. Save and restart application
5. Check if S/P ratio improves

### **Step 2: If Swap Doesn't Work** (2-3 minutes)
1. Close application
2. Run: `python utils/oem_calibration_tool.py --serial FLMT09788 --skip-afterglow`
3. Let it sweep and find optimal positions
4. Restart application

### **Step 3: If Still Failing** (hardware issue)
- Check polarizer wheel is not stuck
- Check servo cable connections
- Check polarizer optics are clean
- Consider running full OEM calibration (with afterglow)

---

## 📋 NEXT STEPS

**Which option would you like to try?**

1. **Quick swap** - I can edit the config for you now
2. **Use hardware positions (S=30, P=120)** - I can update config
3. **Run OEM calibration tool** - I can run it for you
4. **Something else** - Tell me what you'd like to investigate

Let me know and I'll help you execute the fix!

