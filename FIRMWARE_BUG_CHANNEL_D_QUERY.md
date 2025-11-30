# Firmware Bugs: LED Control System Broken

**Date**: 2025-11-28
**Firmware Version**: V1.2
**Controller**: PicoP4SPR

## ❌ CONFIRMED BUG #1: lx Command Does NOT Turn Off Channel A 🔴 CRITICAL

### Problem
The `lx` command (turn off all LEDs) fails to disable Channel A. Channel A remains on after `lx` command.

### Test Evidence (2025-11-28 10:17)
```
1. Turn on Channel A at 255 → LED A is BRIGHT ✅
2. Send lx (turn off all) → LED A stays ON ❌
3. Turn on Channel B at 255 → Both A and B are ON ❌

Expected: lx turns off ALL channels
Actual: lx turns off B, C, D but Channel A remains ON
```

### Impact
**SEVERITY: CRITICAL** - Blocks all calibration and measurement

- ❌ Cannot achieve dark baseline (Channel A always on)
- ❌ Cannot measure individual LED brightness (A contaminates all measurements)
- ❌ Step 3 LED ranking fails (measures A+B, A+C, A+D instead of individual LEDs)
- ❌ Calibration produces invalid results
- ❌ All SPR measurements contaminated by Channel A

### Root Cause
Firmware `lx` command implementation incomplete - only disables channels B, C, D.

### Firmware Fix Required
**PRIORITY: URGENT**

Fix `lx` command to disable ALL four channels including A:
```c
// Current (broken):
lx → disables B, C, D only

// Required (fixed):
lx → disables A, B, C, D
```

---

## ✅ FALSE ALARM: Mode Switch Does NOT Activate LEDs

### Initial Report (INCORRECT)
First test showed P-mode switch activating LEDs.

### Retest Results (CORRECT - 2025-11-28 09:51)
```
S-mode switch (ss): Does NOT activate LEDs ✅
P-mode switch (sp): Does NOT activate LEDs ✅
State restoration: Does NOT occur ✅

TEST CONCLUSION: ✅ NO BUG - Mode switches are safe
```

### Root Cause of False Positive
LEDs were already on from previous testing. Fresh connection test confirms mode switches do NOT activate LEDs.

### Impact on Calibration
**User observation**: "LEDs turn on during Steps 1-3"
**Actual cause**: Step 3 LED brightness ranking (EXPECTED BEHAVIOR)
**Timing**: LEDs turn on around 10-15 seconds into calibration (Step 3 phase)
**Status**: ✅ This is normal - Step 3 intentionally activates LEDs for ranking

---

## ❌ CONFIRMED BUG #1: LED Intensity Query - Channel D Conflict
The intensity query command for Channel D (`id`) conflicts with device identification.

```
ia → Returns '255' (but may be incorrect)
ib → Returns '255' (but may be incorrect)
ic → Returns '255' (but may be incorrect)
id → Returns "P4SPR" (device name, not intensity) ❌
```

#### 3.2 Incorrect Intensity Values
All channels return '255' regardless of actual LED state:

```
After lx (turn off): ia → '255' (WRONG, should be 0)
After lx (turn off): ib → '255' (WRONG, should be 0)
After lx (turn off): ic → '255' (WRONG, should be 0)
```

The queries return 255 even when LEDs are confirmed OFF (or partially off).

#### 3.3 Serial Port Congestion
Rapid queries cause write timeout cascades:

```
2025-11-28 09:46:20,406 :: WARNING :: Batch LED command failed - response: b''
2025-11-28 09:46:22,100 :: ERROR :: error while setting batch LED intensities: Write timeout
2025-11-28 09:46:25,428 :: ERROR :: Error turning off channels: Write timeout
```

Once queries start, the serial buffer fills and all subsequent commands timeout.

### Impact
**SEVERITY: HIGH** - LED query system is completely unusable

- ❌ Cannot verify LED state programmatically
- ❌ Queries return wrong values
- ❌ Queries cause serial port to hang
- ❌ Calibration validation blocked
- ✅ LED control commands still work (la, lb, lc, ld, batch)

---

## Summary of Bugs

| Bug | Severity | Impact | Status |
|-----|----------|--------|--------|
| **lx command doesn't turn off Channel A** | 🔴 CRITICAL | Blocks calibration | ✅ CONFIRMED |
| LED intensity queries broken | 🔴 HIGH | Cannot verify LED state | ✅ CONFIRMED |
| Channel D query returns "P4SPR" | 🔴 HIGH | Cannot query channel D | ✅ CONFIRMED |
| Serial buffer congestion | 🔴 MEDIUM | Commands timeout | ✅ CONFIRMED |
| ~~Mode switch activates LEDs~~ | ~~HIGH~~ | ~~Step 3~~ | ✅ FALSE ALARM |

---

## Workarounds Implemented

### Software Changes

1. **Disabled LED queries in calibration** (`calibration_6step.py`):
```python
# V1.2 firmware queries are BROKEN (2025-11-28)
# DISABLED until firmware fix available
has_led_query = False  # Force disable
```

2. **Timing-based validation**: Wait 50ms after `lx` command instead of querying

3. **Visual confirmation**: User observes LED state instead of programmatic verification

4. **Accept P-mode side effect**: Step 3 LEDs will turn on during mode switch - this is expected until firmware fixed

### Testing
- `test_mode_switch_simple.py` - Confirmed P-mode activates LEDs
- `test_led_commands.py` - Confirmed queries broken and cause timeouts

---

## Firmware Fixes Required

### Priority 1: Fix P-Mode LED Activation
```
Command: sp
Current behavior: Activates LEDs
Expected behavior: Move servo to P-mode WITHOUT affecting LED state
```

### Priority 2: Fix LED Turn-Off Command
```
Command: lx
Current behavior: Leaves LED A on
Expected behavior: Turn off ALL LEDs (A, B, C, D)
```

### Priority 3: Fix LED Intensity Queries
```
Commands: ia, ib, ic, id
Current behavior: Return wrong values or "P4SPR"
Expected behavior: Return actual LED intensity (0-255)

Specific fixes needed:
- Rename 'id' command to avoid conflict with device identification
- Query should return actual intensity, not max capability
- Add serial buffer clearing between commands
```

---

## Testing After Firmware Fix

Run these tests to verify fixes:

1. **Test P-mode switch**:
```bash
python test_mode_switch_simple.py
```
Expected: All tests answer 'N' (no LED activation)

2. **Test LED turn-off**:
```bash
# Visual test: Send lx, verify ALL LEDs turn off
```

3. **Test intensity queries**:
```bash
# Set LED A to 100, query should return ~100
# Turn off, query should return 0
```

---

## Files Modified

- `FIRMWARE_BUG_CHANNEL_D_QUERY.md` - This documentation
- `src/utils/calibration_6step.py` - Disabled queries, accept P-mode side effect
- `src/utils/controller.py` - Skip channel D query workaround
- `test_mode_switch_simple.py` - Test script for mode switch behavior
- `test_led_commands.py` - Comprehensive LED command testing

---

## Impact on Calibration

**Current Behavior** (with bugs):
- Step 3 starts → P-mode switch → LEDs turn on (FIRMWARE BUG)
- Step 3 continues → LED ranking → LEDs flash one at a time (EXPECTED)

**User Observation**: "LEDs turn on during Steps 1-3"
**Root Cause**: P-mode switch at START of Step 3

**Mitigation**: This is acceptable for now since Step 3 needs LEDs on anyway for ranking. The premature activation doesn't affect calibration quality, just timing.

**After Firmware Fix**: LEDs will only turn on during LED ranking phase, not during mode switch.

**DISABLE LED QUERIES ENTIRELY** until firmware is fixed.

### Changes Made

1. **Disabled queries in calibration** (`calibration_6step.py`):
```python
# V1.2 firmware queries are BROKEN - returning wrong values and causing timeouts
# Disabled until firmware fix available
has_led_query = False  # Force disable even if available
```

2. **Skip channel D** (`controller.py`):
```python
def get_all_led_intensities(self):
    # Skip 'd' due to firmware 'id' command conflict
    for ch in ['a', 'b', 'c']:
        ...
    intensities['d'] = -1  # Cannot query
    return intensities
```

3. **Visual confirmation only**: Rely on user observation instead of queries

## Firmware Fix Needed

### Option 1: Rename Intensity Command (Recommended)
Change channel D intensity query from `id` to alternative:
- `i4` (channel 4)
- `ix` (channel D as hex)
- `iw` (channel D as W)

### Option 2: Rename Device ID Command
Change device identification from `id` to:
- `dev` (device)
- `who` (who am I)
- `name` (device name)

### Option 3: Add Context Awareness
Make firmware distinguish between:
- `id\n` at startup → Device identification
- `id\n` during operation → Intensity D query

## Impact

- **Severity**: Low
- **Channels A, B, C**: Fully functional ✅
- **Channel D**: Cannot verify intensity via query ⚠️
- **LED Control**: All channels still work for setting intensity ✅
- **Workaround**: Software skips channel D validation

## Files Modified

1. `src/utils/controller.py` - Skip channel D in `get_all_led_intensities()`
2. `src/utils/calibration_6step.py` - Skip channel D in validation logic

## Testing

Run test to confirm channels A, B, C work:
```bash
python test_mode_switch_simple.py
```

Channels A, B, C can be verified. Channel D requires visual confirmation only.
