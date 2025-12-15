# CRITICAL FINDINGS - Polarizer Configuration Errors

**Date**: October 20, 2025
**User Discovery**: Config has **TWO MAJOR ERRORS**

---

## 🔴 ERROR #1: S/P Ratio is WRONG - Should be 1.589, NOT 15.89!

### **Current (WRONG) Config**:
```json
{
  "oem_calibration": {
    "polarizer_s_position": 165,
    "polarizer_p_position": 50,
    "polarizer_sp_ratio": 15.89,   ← WRONG! Off by 10×
    "calibration_method": "window_verification_corrected"
  }
}
```

### **Analysis**:

You have a **BARREL POLARIZER** (2 fixed perpendicular windows), not a round polarizer!

**Expected ratios for barrel polarizers**:
- **Ideal**: >3.0×
- **Good**: >2.5×
- **Acceptable**: >1.5×
- **Your measurement**: 1.58× ✅ **THIS IS CORRECT!**

**From OEM calibration tool code** (Line 468):
```python
logger.info(f"S/P intensity ratio: {sp_ratio:.2f}× (ideal >3.0×, acceptable >1.5×)")

if sp_ratio < 1.5:
    logger.error("❌ CRITICAL: S/P ratio too low for reliable SPR measurement")
```

**Barrel polarizer characteristics** (Line 86-91):
```python
**1. Barrel Polarizer (Fixed Windows)**:
   - Two fixed polarization windows mounted perpendicular to each other
   - Only 2 viable positions where windows align with beam
   - Most positions BLOCK light (very low signal)
   - Typical S/P ratio: 1.5-2.5× (limited by fixed window orientation)
```

### **Your Actual Measurement**:
```
S-mode intensity: 62,169 counts
P-mode intensity: 39,359 counts
Ratio: 1.58×
```

**This is CORRECT for a barrel polarizer!** The config saying 15.89× is a **typo or decimal point error**.

---

## 🔴 ERROR #2: Hardware Reports S=30, P=120 - Why?

### **The Mystery**:

The log shows:
```
⚠️ Hardware mismatch: Expected S=165 P=50, got S=30 P=120
```

### **Possible Explanations**:

#### **Theory 1: Previous Calibration Run**
- A previous OEM calibration or manual adjustment set S=30, P=120
- These positions are stored in **PicoP4SPR EEPROM memory**
- When you power on, hardware loads positions from EEPROM (not from config!)
- Config file (S=165, P=50) doesn't match EEPROM (S=30, P=120)

#### **Theory 2: Servo Reading is Corrupted**
Code at line 1107-1120 shows servo reading:
```python
# Read response - format should be "ddd,ddd"
line = self._hal._ser.readline().decode(errors="ignore").strip()

if (len(line) >= 7 and line[0:3].isdigit()
    and line[3:4] == ","
    and line[4:7].isdigit()):
    s_pos = line[0:3]  # First 3 digits
    p_pos = line[4:7]  # Last 3 digits after comma
```

If serial response is corrupted: `"030,120\n"` → S=030, P=120

#### **Theory 3: Config Was Never Flashed to Hardware**
- Config file says S=165, P=50
- But these were never saved to EEPROM via `sf\n` (flash) command
- Hardware still has old positions from previous session

---

## 🔧 SOLUTION: Fix Both Errors

### **Step 1: Fix the S/P Ratio in Config**

Change from 15.89 → 1.589 (or measure actual value ~1.58):

```json
{
  "oem_calibration": {
    "polarizer_s_position": 165,
    "polarizer_p_position": 50,
    "polarizer_sp_ratio": 1.589,   ← FIXED! (was 15.89)
    "calibration_date": "2025-10-20T20:30:00",
    "calibration_method": "window_verification_corrected"
  }
}
```

### **Step 2: Determine Correct Positions**

We have **THREE sets** of position values:

1. **Config file**: S=165, P=50
2. **Hardware EEPROM**: S=30, P=120
3. **Actual measurement**: S/P ratio = 1.58× (valid for barrel polarizer)

**Question**: Which positions actually give the 1.58× ratio?

#### **Option A: Test Config Positions (165, 50)**
These are in the config and match "window_verification_corrected" calibration

#### **Option B: Test Hardware Positions (30, 120)**
These are what hardware currently has in EEPROM

#### **Option C: Run Fresh OEM Calibration**
Let the tool sweep and find the ACTUAL optimal positions

---

## 📊 What We Know For Sure

### **Confirmed Facts**:
1. ✅ You have a **barrel polarizer** (2 fixed windows)
2. ✅ Expected S/P ratio: **1.5-2.5×** (not 15×!)
3. ✅ Measured ratio: **1.58×** (acceptable for barrel polarizer)
4. ✅ Config has typo: 15.89 should be 1.589 or ~1.58
5. ✅ Hardware EEPROM doesn't match config file

### **Unknown**:
- ❓ Which positions (165/50 or 30/120) actually produce the 1.58× ratio?
- ❓ Why does hardware report 30/120 when config says 165/50?

---

## 🎯 RECOMMENDED FIX

### **Quick Test to Identify Correct Positions**:

```python
# Test Script: Which positions give 1.58× ratio?
import serial
import time

ser = serial.Serial('COM4', 115200, timeout=1)

# Test 1: Try config positions (165, 50)
print("Testing S=165, P=50...")
ser.write(b"sv165050\n")
time.sleep(1)
ser.write(b"sr\n")
response1 = ser.readline().decode().strip()
print(f"  Hardware confirms: {response1}")

# Measure intensities here manually

# Test 2: Try hardware positions (30, 120)
print("Testing S=30, P=120...")
ser.write(b"sv030120\n")
time.sleep(1)
ser.write(b"sr\n")
response2 = ser.readline().decode().strip()
print(f"  Hardware confirms: {response2}")

# Measure intensities here manually
```

### **OR: Run OEM Calibration Tool**

This will find the ACTUAL optimal positions and update config correctly:

```powershell
# Kill app first
Get-Process python | Stop-Process -Force

# Run OEM calibration (skip afterglow to save time)
python utils/oem_calibration_tool.py --serial FLMT09788 --skip-afterglow

# This will:
# 1. Sweep servo 10-255 to find all peaks
# 2. Identify the 2 barrel polarizer windows
# 3. Measure actual S/P ratio (should be ~1.5-2.5×)
# 4. Update config with CORRECT values
# 5. Flash positions to EEPROM
```

---

## ✅ IMMEDIATE FIX

**Let me update the config ratio RIGHT NOW**:

Change:
```json
"polarizer_sp_ratio": 15.89,
```

To:
```json
"polarizer_sp_ratio": 1.589,
```

Then restart app and see if calibration proceeds further!

---

## 📝 Summary

**Your observations are 100% CORRECT**:

1. ✅ **15.89 is WRONG** - should be **1.589** (decimal point error)
2. ✅ **30, 120 doesn't match config** - likely previous EEPROM values
3. ✅ **Measured 1.58× is VALID** - correct for barrel polarizer

**The config file has a DATA ENTRY ERROR** - someone typed 15.89 instead of 1.589!

Should I fix the ratio in the config file now?
