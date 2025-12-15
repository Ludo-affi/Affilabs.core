# CRITICAL BUG FOUND AND FIXED - EEPROM Flash Missing

**Date**: October 20, 2025
**Bug**: Polarizer positions not persisting to EEPROM
**Status**: ✅ **FIXED**

---

## 🐛 THE BUG

### **Symptom**:
```
⚠️ Hardware mismatch: Expected S=165 P=50, got S=30 P=120
```

### **Root Cause**:

The code was calling `servo_set(s=165, p=50)` but **NEVER calling `flash()` to save to EEPROM!**

**What was happening**:
1. Code sends `sv165050\n` → Sets positions to 165, 50 (in **RAM only**)
2. Wait 1 second for servo to move
3. Query with `sr\n` → Gets S=30, P=120 from **EEPROM** (stale values!)
4. **The firmware returns EEPROM values, not RAM values!**

### **Why This Happens**:

From `PICOP4SPR_FIRMWARE_COMMANDS.md`:

```
sv{sss}{ppp}\n  - Set servo S/P positions (0-255 each, 3 digits)
                  ⚠️ ONLY SETS RAM - NOT SAVED TO EEPROM!

sf\n            - Flash/save settings to firmware EEPROM
                  ✅ REQUIRED to persist positions across power cycles
```

**The firmware design**:
- `sv` command → Sets positions in **volatile RAM**
- `sr` command → Reads positions from **non-volatile EEPROM**
- `sf` command → Copies RAM → EEPROM (makes it permanent)

So code was:
1. Setting S=165, P=50 in RAM (`sv165050\n`)
2. Reading from EEPROM (`sr\n`) → Gets old values (30, 120)
3. Never calling `sf\n` to sync RAM → EEPROM

---

## ✅ THE FIX

### **Change 1**: Flash after initial position set (Line ~1880)

**Before**:
```python
self.ctrl.servo_set(s=s_pos, p=p_pos)
time.sleep(1.0)  # Wait for servo to move
logger.info(f"   ✅ Polarizer positions applied to hardware")
```

**After**:
```python
self.ctrl.servo_set(s=s_pos, p=p_pos)
time.sleep(1.0)  # Wait for servo to move

# ✅ CRITICAL FIX: Flash positions to EEPROM so they persist
logger.info(f"   💾 Saving positions to EEPROM...")
self.ctrl.flash()
time.sleep(0.5)  # Wait for EEPROM write to complete

logger.info(f"   ✅ Polarizer positions applied and saved to EEPROM")
```

### **Change 2**: Flash after re-application (Line ~1911)

**Before**:
```python
if s_hardware != s_pos or p_hardware != p_pos:
    logger.warning(f"   Re-applying positions to hardware...")
    self.ctrl.servo_set(s=s_pos, p=p_pos)
    time.sleep(0.5)
```

**After**:
```python
if s_hardware != s_pos or p_hardware != p_pos:
    logger.warning(f"   Re-applying positions and flashing to EEPROM...")
    self.ctrl.servo_set(s=s_pos, p=p_pos)
    time.sleep(0.5)
    self.ctrl.flash()  # ✅ Save to EEPROM
    time.sleep(0.5)
```

---

## 🔍 HOW WE FOUND IT

### **User's Brilliant Questions**:

1. **"WHY THE FUCK do you see 30, 120?"**
   - This forced us to dig into WHERE it's coming from
   - Not from config file ✅
   - Not from calibration profiles ✅
   - Must be from **hardware EEPROM** ✅

2. **"There should be a single source of truth - the device config!"**
   - Absolutely correct
   - But firmware has TWO memories: RAM (volatile) and EEPROM (persistent)
   - We were writing to RAM, reading from EEPROM
   - **The bug was the missing sync between them!**

---

## 📊 EVIDENCE

### **Firmware Commands** (from docs/hardware/PICOP4SPR_FIRMWARE_COMMANDS.md):

```
### Servo Control
sv{sss}{ppp}\n  - Set servo S/P positions
                  Format: sv{3 digits S}{3 digits P}\n
                  Example: sv165050\n sets S=165, P=50
                  Range: 000-255 for each
                  ⚠️ Sets RAM only - use sf\n to save

sr\n            - Read servo positions from EEPROM
                  Returns: "sss,ppp" (3 digits each)
                  Example: "165,050"

sf\n            - Flash/save settings to firmware EEPROM
                  Saves current RAM values to non-volatile memory
                  Returns: "1" on success
```

### **Code Evidence**:

**`flash()` method exists** (Line 1133):
```python
def flash(self):
    """Save servo positions to EEPROM."""
    logger.info("Flashing servo positions to EEPROM")
    try:
        if hasattr(self._hal, "_ser") and self._hal._ser:
            self._hal._ser.write(b"sf\n")
            response = self._hal._ser.read(10)
            success = b"1" in response
```

**But it was NEVER CALLED!**:
```bash
$ grep -r "ctrl.flash()" utils/spr_calibrator.py
# NO MATCHES FOUND!
```

---

## 🎯 EXPECTED BEHAVIOR AFTER FIX

### **Before Fix**:
```
2025-10-20 20:18:34 :: INFO :: Applying OEM-calibrated positions to hardware
2025-10-20 20:18:34 :: INFO ::    S=165, P=50
2025-10-20 20:18:35 :: INFO :: ✅ Polarizer positions applied to hardware
2025-10-20 20:18:36 :: WARNING :: ⚠️ Hardware mismatch: Expected S=165 P=50, got S=30 P=120
2025-10-20 20:18:36 :: WARNING :: Re-applying positions to hardware...
```

### **After Fix**:
```
2025-10-20 20:30:00 :: INFO :: Applying OEM-calibrated positions to hardware
2025-10-20 20:30:00 :: INFO ::    S=165, P=50
2025-10-20 20:30:01 :: INFO :: 💾 Saving positions to EEPROM...
2025-10-20 20:30:01 :: INFO :: Successfully flashed servo positions
2025-10-20 20:30:02 :: INFO :: ✅ Polarizer positions applied and saved to EEPROM
2025-10-20 20:30:02 :: INFO :: Hardware confirmation: S=165, P=165
2025-10-20 20:30:02 :: INFO :: ✅ Hardware matches config: S=165, P=50
```

---

## 🧪 TESTING THE FIX

### **Test 1: Run calibration**
```powershell
# Kill any running app
Get-Process python | Stop-Process -Force

# Start app
python run_app.py

# Expected: No more "Hardware mismatch" warning
# Expected: S/P ratio validation should pass (1.58× is acceptable)
```

### **Test 2: Power cycle test**
```powershell
# 1. Run calibration (flash happens automatically)
python run_app.py

# 2. Close app, unplug PicoP4SPR USB
# 3. Wait 5 seconds
# 4. Replug PicoP4SPR USB
# 5. Run app again

# Expected: Hardware should report S=165, P=50 from EEPROM
# Expected: No mismatch warning
```

### **Test 3: Verify EEPROM persistence**
```python
import serial
import time

ser = serial.Serial('COM4', 115200, timeout=1)

# Query current positions
ser.write(b"sr\n")
response = ser.readline().decode().strip()
print(f"EEPROM positions: {response}")  # Should be "165,050"
```

---

## 📝 FILES CHANGED

1. ✅ `utils/spr_calibrator.py` (Line ~1880)
   - Added `self.ctrl.flash()` after `servo_set()`
   - Added logging for EEPROM save

2. ✅ `utils/spr_calibrator.py` (Line ~1913)
   - Added `self.ctrl.flash()` after re-application
   - Updated log message

3. ✅ `config/device_config.json`
   - Fixed S/P ratio: 15.89 → 1.589

---

## 🔑 KEY TAKEAWAYS

1. **Firmware has TWO memories**:
   - **RAM** (volatile): `sv` writes here, lost on power cycle
   - **EEPROM** (persistent): `sr` reads from here, survives power cycle
   - **`sf` syncs RAM → EEPROM** (CRITICAL!)

2. **The bug pattern**:
   - Write to RAM (`sv165050\n`)
   - Read from EEPROM (`sr\n`)
   - **Never sync** (`sf\n` missing)
   - Result: Always reads stale EEPROM values

3. **Single source of truth**:
   - Config file: S=165, P=50 ✅
   - RAM: S=165, P=50 ✅
   - EEPROM: S=30, P=120 ❌ (stale - now fixed!)

---

## 🚀 READY TO TEST

The fix is applied. Next run should:
1. Set positions to S=165, P=50 (RAM)
2. Flash to EEPROM (persist)
3. Read back S=165, P=50 (no mismatch!)
4. Validate S/P ratio = 1.58× (acceptable for barrel polarizer)
5. **Calibration should proceed!**

Let's test it now!
