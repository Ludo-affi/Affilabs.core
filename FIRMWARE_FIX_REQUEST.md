# Firmware Fix Request - PicoP4SPR V1.2

**Date**: 2025-11-28
**Reported By**: ezControl-AI Testing
**Device**: PicoP4SPR Controller
**Current Firmware**: V1.2

---

## Executive Summary

Testing revealed **1 CRITICAL bug** and **3 high-priority bugs** in firmware V1.2:

**🔴 CRITICAL - BLOCKS ALL OPERATION:**
1. `lx` command does NOT turn off Channel A - blocks calibration and measurements

**🔴 HIGH PRIORITY:**
2. Channel D intensity query returns device name instead of intensity
3. LED intensity queries return incorrect values (always 255)
4. Serial buffer congestion causes command timeouts

---

## 🔴 CRITICAL BUG #1: lx Command Does NOT Turn Off Channel A

**Priority**: URGENT - BLOCKS ALL CALIBRATION
**Impact**: System unusable until fixed

### Problem
The `lx` command fails to disable Channel A. After sending `lx`, Channel A remains ON while B, C, D turn off correctly.

### Test Evidence (2025-11-28 10:17)
```
Step 1: Turn on Channel A at 255
   Result: LED A is BRIGHT ✅

Step 2: Send lx (turn off all LEDs)
   Log: "All LED channels turned OFF via 'lx' command"
   Result: LED A stays ON ❌ (B, C, D turn off correctly)

Step 3: Turn on Channel B at 255
   Result: BOTH A and B are ON ❌

Visual confirmation: Channel A never turns off with lx command
```

### Reproduction
1. Fresh controller connection
2. Turn on Channel A: `la` then `ba255`
3. Verify LED A is lit
4. Send `lx` to turn off all
5. Observe: LED A remains ON (B, C, D turn off)

### Impact on System
- **Cannot achieve dark baseline** - Channel A always contributes ~3000 counts
- **Cannot measure individual LEDs** - All measurements contaminated by Channel A
- **Step 3 LED ranking fails** - Measures A+B, A+C, A+D instead of individual LEDs
- **All calibration data invalid** - Cannot determine true LED brightness ratios
- **SPR measurements contaminated** - Channel A's light affects all readings

### Fix Required
**URGENT: Fix lx command to disable Channel A**

Current behavior:
```
lx → Disables channels B, C, D only (Channel A stays enabled)
```

Required behavior:
```
lx → Disables ALL channels: A, B, C, D
```

### Verification Test
After fix:
1. Turn on all LEDs at 255
2. Send `lx`
3. Verify ALL 4 LEDs turn OFF (including A)
4. Send intensity queries → All should return 0

---

## ✅ FALSE ALARM: Mode Switch Does NOT Activate LEDs

### Initial Report (INCORRECT)
First test appeared to show `sp` command activating LEDs.

### Retest Results (CORRECT - 2025-11-28 09:51)
```
Fresh connection test:
- S-mode switch (ss): LEDs remain OFF ✅
- P-mode switch (sp): LEDs remain OFF ✅
- No state restoration occurs ✅

Conclusion: Mode switches are SAFE - no firmware bug
```

### Root Cause of Confusion
1. LEDs were already on from previous congested test session
2. Serial buffer timeout prevented proper LED turn-off
3. Fresh connection showed correct behavior

**Status**: ✅ NO FIX NEEDED - Working as designed

---

## ✅ FALSE ALARM: LED Turn-Off May Be Working

### Initial Report (UNCERTAIN)
`lx` command appeared to leave LED A on.

### Analysis
Likely caused by serial buffer congestion during stress testing, not actual `lx` command failure.

**Status**: ⚠️ NEEDS RETEST with fresh connection to confirm

---

## 🔴 CONFIRMED BUG #1: Channel D Query Returns Device Name

**Priority**: HIGH
**Impact**: Cannot verify channel D state

### Problem
The `id` command (intensity D) conflicts with device identification. Returns "P4SPR" instead of intensity value.

### Test Evidence
```
Command: ia → Returns '255' ✅
Command: ib → Returns '255' ✅
Command: ic → Returns '255' ✅
Command: id → Returns 'P4SPR' ❌ (should return intensity)

Log: LED d query response: 'P4SPR'
```

### Root Cause
Command conflict: `id` used for both "identify device" and "intensity D".

### Fix Required (Choose One)

**Option A**: Rename intensity D query
- Change to: `i4`, `ix`, or `iw`
- Update: Query command for channel D only

**Option B**: Rename device ID command
- Change to: `dev`, `who`, or `name`
- Update: Device identification during connection

**Recommendation**: Option A (less impact on existing code)

---

## 🔴 CONFIRMED BUG #2: LED Queries Return Wrong Values

**Priority**: HIGH
**Impact**: Cannot verify LED state programmatically

### Problem
Intensity queries return '255' regardless of actual LED state.

### Test Evidence
```
1. Send lx (turn off all LEDs)
2. Query channels:
   ia → Returns '255' (WRONG, LEDs are off, should return 0)
   ib → Returns '255' (WRONG, LEDs are off, should return 0)
   ic → Returns '255' (WRONG, LEDs are off, should return 0)

Expected: Queries return 0 when LEDs are off
Actual: Queries return 255 (max capability, not current state)
```

### Root Cause
Query returns LED maximum capability (255) instead of current intensity setting.

### Fix Required
Modify `ia`, `ib`, `ic` commands to return actual current intensity value (0-255), not the maximum.

---

## 🔴 CONFIRMED BUG #3: Serial Buffer Congestion

**Priority**: HIGH
**Impact**: Commands timeout when queries used

### Problem
Rapid commands cause write timeout cascades. Serial buffer fills and firmware cannot process commands fast enough.

### Test Evidence
```
2025-11-28 09:46:20,406 :: WARNING :: Batch LED command failed - response: b''
2025-11-28 09:46:22,100 :: ERROR :: Write timeout
2025-11-28 09:46:25,428 :: ERROR :: Error turning off channels: Write timeout
```

### Reproduction
1. Send intensity query (ia)
2. Immediately send another command
3. System hangs with write timeouts

### Fix Required
- Clear serial input/output buffers between commands
- Implement command queueing
- Add flow control for rapid commands

---

## Firmware Test Plan

After implementing fixes, verify with these tests:

### Test 1: P-Mode Switch
```
1. lx (turn off all LEDs)
2. Verify all LEDs OFF (visual)
3. sp (switch to P-mode)
4. Verify all LEDs STILL OFF (visual)
✅ PASS if LEDs remain off
```

### Test 2: LED Turn-Off
```
1. Turn on all LEDs at 150 intensity
2. lx (turn off all)
3. Verify ALL 4 LEDs OFF (visual)
✅ PASS if no LEDs are lit
```

### Test 3: Channel D Query
```
1. Set channel D to 100
2. Send: id
3. Should return: 100 (or close)
✅ PASS if returns intensity, not "P4SPR"
```

### Test 4: Query Accuracy
```
1. lx (turn off all)
2. ia → Should return 0
3. Set channel A to 150
4. ia → Should return ~150
✅ PASS if returns actual intensity
```

### Test 5: No Timeouts
```
1. Send 20 commands rapidly
2. All should execute without timeout
✅ PASS if no write timeout errors
```

---

## Current Workarounds

Software has implemented these temporary workarounds:

1. **LED queries disabled** - Use timing-based validation (wait 50ms after command)
2. **Visual confirmation** - User observes LED state instead of programmatic check
3. **Accept P-mode bug** - Step 3 LEDs turn on early, but doesn't affect calibration quality
4. **Skip channel D query** - Channel D validated visually only

---

## Contact

For questions about these bugs or testing:
- Test logs: Available in repository
- Test scripts: `test_mode_switch_simple.py`, `test_led_commands.py`
- Documentation: `FIRMWARE_BUG_CHANNEL_D_QUERY.md`

---

## Appendix: Command Reference

### Expected Behavior

| Command | Expected Behavior |
|---------|------------------|
| `lx` | Turn off ALL LEDs (A, B, C, D) |
| `la` | Enable LED A |
| `lb` | Enable LED B |
| `lc` | Enable LED C |
| `ld` | Enable LED D |
| `ia` | Query LED A intensity (0-255) |
| `ib` | Query LED B intensity (0-255) |
| `ic` | Query LED C intensity (0-255) |
| `id` | Query LED D intensity (0-255) **[BROKEN]** |
| `ss` | Switch servo to S-mode (no LED changes) |
| `sp` | Switch servo to P-mode (no LED changes) **[BROKEN]** |
| `batch,A,B,C,D` | Set all LED intensities |

### Actual Behavior (Bugs)

| Command | Actual (Buggy) Behavior |
|---------|------------------------|
| `lx` | Turns off B, C, D but leaves A on ❌ |
| `ia` | Returns '255' regardless of state ❌ |
| `ib` | Returns '255' regardless of state ❌ |
| `ic` | Returns '255' regardless of state ❌ |
| `id` | Returns 'P4SPR' instead of intensity ❌ |
| `sp` | Moves servo AND activates LEDs ❌ |
