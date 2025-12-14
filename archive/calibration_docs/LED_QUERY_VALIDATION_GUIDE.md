# LED Query Side Effect Validation Guide

**Purpose:** Validate if firmware query commands activate LEDs before updating firmware
**Date:** November 28, 2025
**Status:** Ready for testing

---

## Quick Start

### Option 1: Quick Visual Test (Recommended)
```powershell
.venv312\Scripts\python.exe test_query_quick.py
```
- **Duration:** 30 seconds
- **What it does:** Turns off LEDs, queries LED A, asks if you saw it turn on
- **Best for:** Quick validation

### Option 2: Comprehensive Test
```powershell
.venv312\Scripts\python.exe test_query_side_effect.py
```
- **Duration:** 5 minutes
- **What it does:** Tests all 4 query commands, control tests, alternative hypotheses
- **Best for:** Thorough analysis

---

## What You're Testing

### The Hypothesis
**Suspected Bug:** Firmware query commands (`ia`, `ib`, `ic`, `id`) activate LED channels as a side effect

### Expected Behavior (NO BUG)
```
1. Send: lx\n         → All LEDs OFF
2. Send: ia\n         → LED A stays OFF (read-only query)
3. Response: 000      → Intensity is 0, LED still off
```

### Buggy Behavior (BUG EXISTS)
```
1. Send: lx\n         → All LEDs OFF
2. Send: ia\n         → LED A turns ON! (side effect)
3. Response: 000      → Intensity reported as 0, but LED is on
```

---

## Test Instructions

### Setup
1. Connect hardware (PicoP4SPR controller + detector)
2. Close any other software using the controller
3. Position yourself to clearly see all 4 LEDs on the device
4. Run test script

### During Test
**CRITICAL:** Watch the physical LEDs, not the screen!

1. **Phase 1: Baseline**
   - LEDs turn off
   - ✅ Confirm: All LEDs are dark

2. **Phase 2: Query Command**
   - Script sends `ia\n` (query LED A)
   - 👀 **WATCH LED A** - Does it turn on?
   - Record your observation

3. **Phase 3: All Queries**
   - Script sends `ia\n`, `ib\n`, `ic\n`, `id\n`
   - 👀 **WATCH ALL LEDs** - Do any turn on?
   - Record your observation

4. **Phase 4: Control Test**
   - Script sends `batch:0,50,0,0\n`
   - LED B should turn on (confirms LEDs work)
   - ✅ Confirm: LED B is on

---

## Interpreting Results

### Result 1: LEDs Turn On During Query
```
Phase 2: LED A turned on after ia? YES
Phase 3: Any LEDs on after queries? YES
```

**Conclusion:** 🔴 **FIRMWARE BUG CONFIRMED**

**What it means:**
- Query commands have side effects
- Workaround is CORRECT (keep queries disabled)
- Firmware needs updating

**Action Required:**
1. ✅ Keep `has_led_query = False` in calibration
2. 🔧 Update firmware to fix query commands
3. 🔄 Re-run this test after firmware update
4. ✅ Re-enable queries once firmware fixed

---

### Result 2: LEDs Stay Off During Query
```
Phase 2: LED A turned on after ia? NO
Phase 3: Any LEDs on after queries? NO
```

**Conclusion:** 🟢 **NO FIRMWARE BUG**

**What it means:**
- Query commands are read-only (correct behavior)
- Safe to re-enable queries in calibration
- LEDs turning on during calibration caused by something else

**Action Required:**
1. ❓ Investigate other causes for LED activation
2. ✅ Can re-enable `has_led_query = True` if desired
3. 🔍 Check other firmware commands in Steps 1-3

---

## Firmware Commands Reference

### Query Commands (Being Tested)
| Command | Purpose | Expected Behavior |
|---------|---------|-------------------|
| `ia\n` | Query LED A intensity | Read-only, LED stays off |
| `ib\n` | Query LED B intensity | Read-only, LED stays off |
| `ic\n` | Query LED C intensity | Read-only, LED stays off |
| `id\n` | Query LED D intensity | Read-only, LED stays off |

### Control Commands (Known Safe)
| Command | Purpose | Expected Behavior |
|---------|---------|-------------------|
| `lx\n` | Turn off all LEDs | All LEDs turn off |
| `la\n` | Enable LED A channel | Channel enabled (but LED may stay off until intensity set) |
| `ba128\n` | Set LED A to intensity 128 | LED A turns on at 50% brightness |
| `batch:A,B,C,D\n` | Set all LEDs | LEDs turn on at specified intensities |

---

## Firmware Fix (If Bug Confirmed)

### Current (Buggy) Implementation
```c
// SUSPECTED BUG in firmware:
if (cmd == 'ia') {
    led_a_enabled = true;  // ❌ Side effect!
    return led_a_intensity;
}
```

### Correct Implementation
```c
// CORRECT implementation:
if (cmd == 'ia') {
    // Just return intensity, don't modify state
    return led_a_intensity;  // ✅ Read-only
}
```

### How to Fix
1. Update firmware V1.1+ for all query commands
2. Remove any `led_x_enabled = true` from query handlers
3. Ensure queries only read state, never modify it
4. Re-flash controller
5. Re-run validation test

---

## Troubleshooting

### Test Script Won't Connect
```
❌ Failed to open controller connection
```

**Solutions:**
- Check USB cable is connected
- Close main software if running
- Try different USB port
- Check controller type in script (PicoP4SPR vs ArduinoP4SPR)

### Can't See LEDs Clearly
**Solutions:**
- Dim room lights
- Position device for better viewing angle
- Use phone camera (some LEDs more visible on camera)
- Have another person watch while you run test

### Uncertain About LED State
**Solutions:**
- Re-run test (it's quick)
- Use test_query_quick.py for simpler version
- Compare LED brightness before/after query
- Test one LED at a time

---

## After Testing

### If Bug Confirmed
1. Document firmware version with bug
2. Keep workaround in place (`has_led_query = False`)
3. Share test results with firmware developer
4. Request firmware update
5. Re-test after update

### If No Bug Found
1. Document firmware version working correctly
2. Investigate other causes:
   - Check if `turn_on_channel()` is called unexpectedly
   - Review calibration logs for unexpected commands
   - Test with serial monitor/logic analyzer
3. Consider re-enabling queries:
   - Change `has_led_query = False` to `has_led_query = hasattr(ctrl, 'get_all_led_intensities')`
   - Test calibration Steps 1-3
   - Verify LEDs stay off during verification

---

## Test Data Collection

### Record These Details
- **Date:** _______________
- **Firmware Version:** _______________
- **Controller Type:** PicoP4SPR / ArduinoP4SPR
- **Test Result:** Bug Confirmed / No Bug
- **LED A Query:** ON / OFF
- **All LEDs Query:** ON / OFF
- **Notes:** _______________

---

## Summary

**Goal:** Determine if firmware query commands have side effects
**Method:** Visual observation of physical LEDs during query
**Duration:** 30 seconds (quick) to 5 minutes (comprehensive)
**Decision:** Keep workaround if bug confirmed, re-enable queries if no bug

**Run the test now:**
```powershell
.venv312\Scripts\python.exe test_query_quick.py
```

**Watch the LEDs closely! Your observation determines the next steps.**
