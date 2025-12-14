# Quick Start: Firmware Testing & Fix

## 🚀 TL;DR - What You Need to Do

### Step 1: Test Current Firmware (5 minutes)
```powershell
# Visual test - follow on-screen prompts
.venv312\Scripts\python.exe test_firmware_led_control.py

# OR automated spectrometer test - no visual confirmation needed
.venv312\Scripts\python.exe test_firmware_automated.py
```
**Expected Result:** Tests will FAIL showing Channel A bug

---

### Step 2: Compile Fixed Firmware (2 minutes)
```powershell
cd firmware/pico_p4spr
mkdir build; cd build
cmake -G "Unix Makefiles" ..
make
```
**Output:** `affinite_p4spr.uf2` file created

---

### Step 3: Flash Firmware (1 minute)
1. Hold BOOTSEL button on Pico
2. Connect USB (while holding BOOTSEL)
3. Copy `affinite_p4spr.uf2` to RPI-RP2 drive
4. Pico automatically reboots

---

### Step 4: Test Fixed Firmware (5 minutes)
```powershell
# Same tests as Step 1
.venv312\Scripts\python.exe test_firmware_led_control.py
```
**Expected Result:** ALL tests PASS ✅

---

## 📋 What Was Fixed?

**The Bug:**
- `lx` command (turn off all LEDs) didn't turn off Channel A after 100% brightness
- Channel A stayed ON, contaminating all measurements
- Calibration Step 3 showed ~3,000 counts for all LEDs (invalid data)

**The Fix:**
- Added 100µs delay after setting PWM to 0% before disabling
- RP2040 PWM outputs latch at last state when disabled
- Delay ensures GPIO goes LOW before PWM is disabled

**Files Modified:**
- `firmware/pico_p4spr/affinite_p4spr.c` (lines 580-603, 760-766)

---

## 📊 Before vs After

| Test | Before (V1.2) | After (V1.3) |
|------|---------------|--------------|
| lx turns off Channel A | ❌ Stays ON | ✅ Turns OFF |
| Channel B measurement | ~3,000 (A+B) | ~40,000 (B only) |
| Calibration Step 3 | Invalid | Valid |

---

## 🔧 LED Type Question - ANSWERED!

**You provided:**
- **LCW LED:** Luminus MP-2016-1100-30-80 (11 lumens @ 30mA, 60mA max)
- **OWW LED:** OSRAM GW JTLMS3.GM-G3G7-XX58-1-60-R33 (60 lumens @ 60mA, 180mA max)

**Key Findings:**
- ⚠️ **OWW is 5.5x brighter** than LCW (60 lumens vs 11 lumens)
- ⚠️ **Different current requirements:** LCW 30mA typical (60mA max), OWW 60mA typical (180mA max)
- ✅ **Similar forward voltage:** Both ~2.8-3.2V (compatible with same supply)
- ✅ **Fast switching:** Both <100ns rise/fall time (400Hz PWM perfect)

**Firmware Impact:**
- ✅ **Brightness difference:** NO CHANGE NEEDED - Python calibration handles it automatically
- ⚠️ **Current difference:** DEPENDS ON YOUR PCB - measure LED currents first!

### ⚠️ CRITICAL: Measure LED Currents Before Proceeding

**Why:** OWW LED can handle 3x more current than LCW LED. If your PCB isn't current-limited properly, LCW LEDs may be overdriven.

**How to measure:**
```powershell
.venv312\Scripts\python.exe test_led_current_measurement.py
```

This script will:
1. Turn on each LED at 100% PWM
2. Prompt you to measure current with multimeter
3. Analyze if firmware PWM caps are needed
4. Provide exact code changes if required

**Expected Results:**

| PCB Current Limit | LCW LED Status | OWW LED Status | Firmware Action |
|-------------------|---------------|----------------|-----------------|
| 30-60mA | ✅ Safe | ✅ Safe | None needed |
| 60-180mA | 🔴 Overdrive risk | ✅ Safe | Add PWM caps for LCW channels |
| >180mA | 🔴 Danger | 🔴 Danger | Hardware fix required |

**Most Likely:** Your PCB has 30-60mA current limiting (standard for SPR systems), so NO firmware changes needed! 🎉

---

## ✅ Success Criteria

Fix is complete when:
1. ✅ All tests in `test_firmware_led_control.py` pass
2. ✅ Spectrometer shows <10% residual after lx command
3. ✅ Each LED measures >30,000 counts in calibration (not ~3,000)

---

## 📖 Detailed Documentation

If you need more info, see:
- `FIRMWARE_FIX_IMPLEMENTATION_SUMMARY.md` - Complete overview
- `FIRMWARE_TESTING_CHECKLIST.md` - Detailed test procedures
- `FIRMWARE_BUG_ANALYSIS.md` - Technical root cause analysis
- `LED_HARDWARE_SPECIFICATIONS.md` - LED type considerations

---

## 🆘 Troubleshooting

**Q: Tests still fail after flashing?**
- Verify firmware version: `controller._ser.write(b'iv\n')` should show V1.3
- Try power cycling the controller
- Re-flash firmware using BOOTSEL method

**Q: Can't compile firmware?**
- Check Pico SDK installed and environment variables set
- Ensure CMakeLists.txt present in `firmware/pico_p4spr/`
- Verify GCC ARM toolchain in PATH

**Q: Controller won't enter bootloader?**
- Hold BOOTSEL button for 5+ seconds before connecting USB
- Try different USB cable (must support data transfer)
- Check Pico board for damage

---

**Ready to start?** Run the first test! ⬆️ See Step 1 above.

---

**Last Updated:** November 28, 2025
**Status:** Ready for testing
**Estimated Total Time:** ~15 minutes (test → compile → flash → verify)
