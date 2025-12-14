# Firmware V1.2 Testing & Compilation Checklist

## 🔍 PRE-COMPILATION TESTING (Current Firmware V1.2)

### Purpose
Establish baseline measurements to document the bug before applying the fix.

### Test 1: Visual Confirmation Test
**Script:** `test_firmware_led_control.py`

**What it tests:**
- Individual LED on/off for all 4 channels
- Critical lx bug (Channel A stays on after 100% brightness)
- Channel isolation (A doesn't contaminate B)
- Batch command control
- Rapid switching responsiveness
- Brightness level control

**How to run:**
```powershell
.venv312\Scripts\python.exe test_firmware_led_control.py
```

**Expected results (BEFORE fix):**
- ❌ TEST 2 FAILED: Channel A does NOT turn off after lx command at 100%
- ❌ TEST 3 FAILED: Channel A contaminates Channel B measurement
- ⚠️ Other tests may show issues

**Time required:** ~5-10 minutes (includes visual confirmations)

---

### Test 2: Automated Spectrometer Test
**Script:** `test_firmware_automated.py`

**What it tests:**
- Objective measurements using USB4000 spectrometer
- Quantifies Channel A residual intensity after lx command
- Measures cross-contamination between channels
- Validates batch command with photon counts

**How to run:**
```powershell
.venv312\Scripts\python.exe test_firmware_automated.py
```

**Expected results (BEFORE fix):**
- 🔴 lx Command FAILED: ~80-100% of Channel A intensity remains after lx
- 🔴 Channel Isolation FAILED: B measurement shows A+B instead of just B
- Measurements will show ~3000 counts for all LEDs (contaminated by Channel A)

**Time required:** ~3-5 minutes (fully automated)

---

### Test 3: Quick LED Brightness Test
**Script:** `test_led_brightness.py` (already exists)

**How to run:**
```powershell
.venv312\Scripts\python.exe test_led_brightness.py
```

**Expected results (BEFORE fix):**
- ❌ TEST 4: lx command sent, but Channel A stays ON
- ❌ Channel B turns on → Both A and B are ON (should be only B)

**Time required:** ~1 minute

---

## 🔧 FIRMWARE CHANGES APPLIED

### Modified File
`firmware/pico_p4spr/affinite_p4spr.c`

### Changes Made

#### 1. Function `led_on()` - Lines 578-599
**Before:**
```c
if (ch_led != 'a'){
    pwm_set_chan_level(LED_A_SLICE, LED_A_CH, 0);
    pwm_set_enabled(LED_A_SLICE, false);
    led_a_enabled = false;
}
```

**After:**
```c
if (ch_led != 'a'){
    pwm_set_chan_level(LED_A_SLICE, LED_A_CH, 0);
    sleep_us(100);  // Wait 1 PWM cycle @ 400Hz to ensure LOW state
    pwm_set_enabled(LED_A_SLICE, false);
    led_a_enabled = false;
}
```

**Applied to:** All 4 channels (A, B, C, D)

#### 2. Function `led_batch_set()` - Lines 755-764
**Before:**
```c
// Turn off all LEDs first
pwm_set_chan_level(LED_A_SLICE, LED_A_CH, 0);
pwm_set_chan_level(LED_B_SLICE, LED_B_CH, 0);
pwm_set_chan_level(LED_C_SLICE, LED_C_CH, 0);
pwm_set_chan_level(LED_D_SLICE, LED_D_CH, 0);

pwm_set_enabled(LED_A_SLICE, false);
// ... B, C, D
```

**After:**
```c
// Turn off all LEDs first
pwm_set_chan_level(LED_A_SLICE, LED_A_CH, 0);
pwm_set_chan_level(LED_B_SLICE, LED_B_CH, 0);
pwm_set_chan_level(LED_C_SLICE, LED_C_CH, 0);
pwm_set_chan_level(LED_D_SLICE, LED_D_CH, 0);
sleep_us(100);  // Wait 1 PWM cycle @ 400Hz to ensure all LOW

pwm_set_enabled(LED_A_SLICE, false);
// ... B, C, D
```

### Root Cause Explanation
RP2040 PWM outputs **retain their last state** when disabled. If PWM is disabled while outputting HIGH (100% duty cycle), the GPIO pin stays latched at HIGH. The fix adds a 100µs delay (1 PWM cycle @ 400Hz = 2.5ms period) after setting duty cycle to 0% to ensure the PWM output goes LOW before the peripheral is disabled.

---

## 🛠️ FIRMWARE COMPILATION

### Build Environment Setup

#### Prerequisites
1. **Pico SDK** (already installed if you've built before)
2. **CMake** (version 3.13 or higher)
3. **GCC ARM compiler** (`arm-none-eabi-gcc`)

#### Build Commands
```powershell
cd firmware/pico_p4spr

# Clean previous build (optional)
Remove-Item -Recurse -Force build -ErrorAction SilentlyContinue

# Create build directory
mkdir build
cd build

# Configure CMake
cmake -G "Unix Makefiles" ..

# Build firmware
make
```

#### Expected Output
```
[100%] Building C object CMakeFiles/affinite_p4spr.dir/affinite_p4spr.c.obj
[100%] Linking CXX executable affinite_p4spr.elf
[100%] Built target affinite_p4spr
```

#### Output Files
- `affinite_p4spr.uf2` - Flash this to Pico
- `affinite_p4spr.elf` - Debug symbols
- `affinite_p4spr.bin` - Raw binary

---

## 📲 FIRMWARE FLASHING

### Method 1: USB Boot Mode (Manual)
1. Disconnect Pico from USB
2. Hold BOOTSEL button on Pico
3. Connect Pico to USB while holding BOOTSEL
4. Pico appears as USB mass storage device (RPI-RP2)
5. Copy `affinite_p4spr.uf2` to the drive
6. Pico automatically reboots with new firmware

### Method 2: Software Reboot to Bootloader
```python
from src.utils.controller import ArduinoController

controller = ArduinoController(port='COM10')
controller.open()
controller._ser.write(b'iB\n')  # Reboot to bootloader command
# Then copy .uf2 file to RPI-RP2 drive
```

---

## ✅ POST-COMPILATION TESTING (Fixed Firmware)

### Test 1: Visual Confirmation Test (Re-run)
```powershell
.venv312\Scripts\python.exe test_firmware_led_control.py
```

**Expected results (AFTER fix):**
- ✅ TEST 1 PASSED: All channels turn on/off independently
- ✅ TEST 2 PASSED: lx command turns off all LEDs including Channel A
- ✅ TEST 3 PASSED: Channel isolation working (no A contamination in B)
- ✅ TEST 4 PASSED: Batch commands working correctly
- ✅ TEST 5 PASSED: Rapid switching responsive
- ✅ TEST 6 PASSED: Brightness levels accurate

**Success criteria:** ALL 6 tests pass

---

### Test 2: Automated Spectrometer Test (Re-run)
```powershell
.venv312\Scripts\python.exe test_firmware_automated.py
```

**Expected results (AFTER fix):**
- ✅ lx Command PASSED: <10% residual intensity after lx command
- ✅ Channel Isolation PASSED: B measurement shows only B (no A contamination)
- ✅ Sequential Switching PASSED: Each LED measures independently
- ✅ Batch Commands PASSED: All LEDs turn off completely with batch:0,0,0,0

**Success criteria:** ALL 4 tests pass

---

### Test 3: Calibration Step 3 Validation
**Script:** Run actual calibration to verify LED ranking works

```powershell
.venv312\Scripts\python.exe test_calibration_steps_1_4.py
```

**Expected results (AFTER fix):**
- ✅ Channel A: ~40,000+ counts at target integration time
- ✅ Channel B: ~40,000+ counts (different wavelength, similar photon output)
- ✅ Channel C: ~40,000+ counts
- ✅ Channel D: ~40,000+ counts
- ✅ All measurements show DISTINCT intensities (not ~3000 counts for all)

**Success criteria:** Each LED measures >30,000 counts at optimized integration time

---

## 📊 COMPARISON TABLE

### Before Fix (V1.2 with Bug)

| Test | Channel A | Channel B | Channel C | Channel D | Status |
|------|-----------|-----------|-----------|-----------|--------|
| lx command @ 100% | Stays ON | Turns OFF | Turns OFF | Turns OFF | ❌ FAIL |
| Channel isolation | Contaminates B | OK | OK | OK | ❌ FAIL |
| Spectrometer counts | ~3000 (A+B) | ~3000 (A+C) | ~3000 (A+D) | ~3000 (A+D) | ❌ FAIL |
| Calibration Step 3 | Invalid | Invalid | Invalid | Invalid | ❌ FAIL |

### After Fix (V1.3 Expected)

| Test | Channel A | Channel B | Channel C | Channel D | Status |
|------|-----------|-----------|-----------|-----------|--------|
| lx command @ 100% | Turns OFF | Turns OFF | Turns OFF | Turns OFF | ✅ PASS |
| Channel isolation | No contamination | OK | OK | OK | ✅ PASS |
| Spectrometer counts | ~40,000 | ~40,000 | ~40,000 | ~40,000 | ✅ PASS |
| Calibration Step 3 | Valid | Valid | Valid | Valid | ✅ PASS |

---

## 🚨 ROLLBACK PROCEDURE

If the fix causes any issues:

1. Reflash original V1.2 firmware backup (if you have one)
2. Or revert the code changes in `affinite_p4spr.c`:
   - Remove all `sleep_us(100);` lines added in the fix
   - Recompile and flash

3. Document the issue and investigate further

---

## 📝 VERSION TRACKING

### Current Firmware
- **Version:** V1.2
- **Date:** November 2025
- **Status:** Contains PWM shutdown bug

### Fixed Firmware
- **Version:** V1.3 (suggested)
- **Date:** November 28, 2025
- **Changes:** Added sleep_us(100) delays in led_on() and led_batch_set()
- **Status:** Bug fix for Channel A lx command failure

**Update firmware version string:**
In `affinite_p4spr.c` line 35, change:
```c
const char* VERSION = "V1.2";  // Updated: Added rank command for fast LED calibration
```
To:
```c
const char* VERSION = "V1.3";  // Fixed: PWM shutdown bug - LEDs now turn off properly
```

---

## 🎯 ACCEPTANCE CRITERIA

The firmware fix is considered **SUCCESSFUL** if:

1. ✅ All 6 visual tests pass in `test_firmware_led_control.py`
2. ✅ All 4 automated tests pass in `test_firmware_automated.py`
3. ✅ Channel A turns off completely after lx command at 100% brightness
4. ✅ Channel B measurement shows no Channel A contamination
5. ✅ Calibration Step 3 LED ranking produces distinct intensities (>30,000 counts each)
6. ✅ Controller remains responsive during rapid LED switching
7. ✅ No regression in other LED control functions

**If ANY test fails, DO NOT proceed to production use!**

---

## 📞 TROUBLESHOOTING

### Issue: Firmware won't compile
- Check Pico SDK installation and environment variables
- Ensure CMakeLists.txt is present
- Verify GCC ARM toolchain is in PATH

### Issue: Pico won't enter bootloader mode
- Try holding BOOTSEL button for 5+ seconds
- Disconnect/reconnect USB cable
- Check USB cable supports data (not just power)

### Issue: Test scripts can't connect to controller
- Verify COM port number (may change after firmware flash)
- Check USB cable connection
- Restart Python script
- Check controller responds to `iv` command

### Issue: Tests still fail after flashing fixed firmware
- Verify firmware version with `iv` command shows V1.3
- Double-check .uf2 file was copied successfully
- Measure GPIO 28 voltage with multimeter (should be 0V when off)
- Try power cycling the controller

---

## ✅ CHECKLIST SUMMARY

### Pre-Compilation
- [ ] Run `test_led_brightness.py` - document current bug
- [ ] Run `test_firmware_led_control.py` - record failing tests
- [ ] Run `test_firmware_automated.py` - record spectrometer measurements
- [ ] Save baseline data for comparison

### Compilation
- [ ] Review code changes in `affinite_p4spr.c`
- [ ] Update version string to V1.3
- [ ] Build firmware successfully
- [ ] Verify .uf2 file created

### Flashing
- [ ] Backup current firmware (if possible)
- [ ] Flash new firmware to Pico
- [ ] Verify device reconnects
- [ ] Check firmware version shows V1.3

### Post-Compilation
- [ ] Run `test_led_brightness.py` - verify lx works
- [ ] Run `test_firmware_led_control.py` - verify all 6 tests pass
- [ ] Run `test_firmware_automated.py` - verify spectrometer measurements
- [ ] Run `test_calibration_steps_1_4.py` - verify calibration works
- [ ] Document improvements in measurements

### Final Validation
- [ ] All acceptance criteria met
- [ ] No regressions in other functionality
- [ ] Controller responsive and stable
- [ ] Ready for production calibration use

---

**Last Updated:** November 28, 2025
**Author:** GitHub Copilot AI
**Firmware Version:** V1.2 → V1.3 (PWM shutdown bug fix)
