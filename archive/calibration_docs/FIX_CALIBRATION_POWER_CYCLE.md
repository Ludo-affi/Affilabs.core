# 🔧 FIX CALIBRATION FAILURE - REQUIRED STEPS

## ❌ Current Problem

Your calibration is failing with:
```
ERROR: Failed to set S-mode - controller did not confirm
```

## 🎯 Root Cause

The controller firmware **cached old EEPROM positions** when it booted:
- **Old EEPROM values**: S=120°, P=60° (inverted - WRONG)
- **New device_config**: S=89°, P=179° (correct)

The application **wrote new values to EEPROM**, but the controller firmware **didn't reload them**.

When calibration calls `set_mode('s')`:
1. Firmware tries to move servo to OLD cached position (120°)
2. This fails because it's the wrong position
3. Controller returns error
4. Calibration fails

## ✅ Solution: Power Cycle Controller

The firmware must be **restarted** to reload EEPROM values from flash.

### Steps to Fix:

```
1. Close the ezControl application

2. Unplug the controller USB cable
   (Remove from computer, not just controller power button)

3. Wait 5 seconds
   (Let capacitors drain, ensure full power off)

4. Plug the controller USB cable back in
   (Firmware will boot and load new EEPROM values)

5. Restart the ezControl application

6. Run calibration
   ✅ Will work now - firmware using correct positions!
```

## 🔍 How to Verify It Worked

When you restart the application, check the console logs:

**If EEPROM matches device_config (after power cycle):**
```
✅ EEPROM matches device_config - no update needed
   Servo positions: S=89°, P=179° (🔒 IMMUTABLE)
```

**During calibration, you should see:**
```
🔍 POLARIZER POSITION VALIDATION: S-MODE
   Device Config Source: VERIFIED ✅
   S-mode position: 89°
   P-mode position: 179°
   Validation: PASSED ✅

📡 Controller response to set_mode('s'): b'1' (after 1 attempts)
✅ Controller confirmed: S-mode servo moved to position from device_config
```

## 🚨 Important Notes

1. **Don't skip the power cycle** - closing/reopening the app won't work
2. **Wait the full 5 seconds** - partial power drain won't reload EEPROM
3. **The positions are correct in your device_config** - this is NOT a position problem
4. **This is a one-time fix** - once firmware reloads, positions will be correct

## 📚 Technical Details

For the full technical explanation, see:
- `SERVO_ARCHITECTURE_CRITICAL_RULE.md` - Complete architecture documentation
- Section: "WHY DID CALIBRATION FAIL? → Root Cause: Firmware Caches EEPROM at Boot"

---

**After power cycle, your calibration will work correctly!**
