# Calibration LED Activation Analysis - Steps 1 & 2

**Date:** November 28, 2025
**Issue:** LEDs turning on unexpectedly during calibration Steps 1-2
**Status:** 🔍 Investigation Complete - Test Script Created

---

## Problem Description

During calibration Steps 1 and 2, all LEDs appear to turn on when they should remain OFF. This is unexpected behavior since:

- **Step 1:** Hardware validation - LEDs should be forced OFF
- **Step 2:** Wavelength calibration - No LEDs should be on (dark measurement)

---

## Investigation Findings

### Step 1: Hardware Validation & LED Verification

**Location:** `src/utils/calibration_6step.py` lines 586-651

**Expected Behavior:**
```python
# Line 605: Force all LEDs OFF
ctrl.turn_off_channels()
time.sleep(0.2)

# Line 608-643: VERIFY LEDs are off (V1.1+ firmware)
led_state = ctrl.get_all_led_intensities()
all_off = all(intensity == 0 for intensity in led_state.values())
```

**Key Code:**
1. Calls `turn_off_channels()` to disable all LEDs
2. Waits 200ms for command to process
3. Queries LED state using `get_all_led_intensities()` (V1.1+ firmware)
4. Retries up to 5 times if LEDs aren't confirmed off
5. Raises error if verification fails

---

### Step 2: Wavelength Calibration

**Location:** `src/utils/calibration_6step.py` lines 653-704

**Expected Behavior:**
- Reads wavelength data from spectrometer EEPROM
- No LED activation should occur
- No measurements taken (pure metadata reading)

**Observation:** Step 2 does NOT call any LED commands - purely detector calibration.

---

### Quick Dark Baseline (Legacy Function)

**Location:** `src/utils/calibration_6step.py` lines 135-250

**Note:** This function (`measure_quick_dark_baseline`) is defined but **NOT CALLED** in the main calibration flow. It's legacy code from an older implementation.

**If it were called, it would:**
1. Turn off all LEDs via `turn_off_channels()`
2. Verify LEDs are off (V1.1+ firmware query)
3. Wait for LED decay (LED_DELAY)
4. Measure 3 dark scans at 100ms integration

---

## Controller Implementation Analysis

### PicoP4SPR Controller

**Location:** `src/utils/controller.py` lines 771-1177

#### `turn_off_channels()` - Line 1027
```python
def turn_off_channels(self):
    cmd = f"lx\n"  # Send 'lx' command to firmware
    self._ser.write(cmd.encode())
    success = self._ser.read() == b'1'
    if success:
        self._channels_enabled.clear()
    return success
```

**Firmware Command:** `lx` = disable all LED channels

---

#### `turn_on_channel(ch)` - Line 895
```python
def turn_on_channel(self, ch='a'):
    # Skip if already enabled
    if ch in self._channels_enabled:
        return True

    cmd = f"l{ch}\n"  # Send 'la', 'lb', 'lc', or 'ld'
    self._ser.write(cmd.encode())
    response = self._ser.read(10)
    success = b'1' in response
    if success:
        self._channels_enabled.add(ch)
    return success
```

**Firmware Commands:**
- `la` = enable LED A
- `lb` = enable LED B
- `lc` = enable LED C
- `ld` = enable LED D

---

#### `get_all_led_intensities()` - Line 964
```python
def get_all_led_intensities(self):
    intensities = {}
    for ch in ['a', 'b', 'c', 'd']:
        intensity = self.get_led_intensity(ch)
        if intensity < 0:
            return None
        intensities[ch] = intensity
    return intensities
```

**Queries each LED:** Sends `ia\n`, `ib\n`, `ic\n`, `id\n` to read current intensity

---

#### `set_intensity(ch, raw_val)` - Line 1044

**⚠️ CRITICAL CODE PATH:**
```python
def set_intensity(self, ch='a', raw_val=1):
    # ... validation ...

    # CRITICAL: Enable channel FIRST, then set intensity
    # Firmware only applies PWM if channel is enabled
    self.turn_on_channel(ch=ch)  # ⚠️ ALWAYS CALLS turn_on_channel()

    cmd = f"b{ch}{int(raw_val):03d}\n"  # e.g., "ba128\n"
    self._ser.write(cmd.encode())
    return ok
```

**Issue Identified:**
1. Every `set_intensity()` call FIRST calls `turn_on_channel()`
2. This enables the LED channel (firmware sets `led_x_enabled = true`)
3. Even if intensity is 0, the channel gets enabled

**Firmware Commands:**
- `ba000\n` = set LED A to intensity 0 (but channel enabled)
- `ba128\n` = set LED A to intensity 128

---

## Potential Root Causes

### 1. **Firmware Query Commands Triggering LEDs**

**Hypothesis:** The `get_led_intensity()` queries (`ia`, `ib`, `ic`, `id`) might be triggering LED activation as a side effect.

**Evidence:**
- Step 1 queries LED state 4 times (one per channel)
- If firmware interprets `ia` as "initialize LED A" instead of "query intensity A", LEDs would turn on

**Test:** Run `test_led_commands.py` and observe if LEDs turn on during `get_all_led_intensities()` query

---

### 2. **turn_off_channels() Not Working Properly**

**Hypothesis:** The `lx` command doesn't fully disable all LEDs in firmware.

**Evidence:**
- Firmware might clear intensity but leave `led_x_enabled = true`
- Subsequent query commands could reactivate LEDs

**Test:** Verify firmware response to `lx` command with logic analyzer or serial monitor

---

### 3. **Timing Issue - LEDs Not Fully Off**

**Hypothesis:** 200ms delay (line 607) isn't enough for LEDs to turn off.

**Evidence:**
- LEDs may have electrical decay time > 200ms
- Firmware might process `lx` command slowly

**Test:** Increase delay to 500ms and re-test

---

### 4. **Firmware Bug - LED Query Enables Channel**

**Hypothesis:** Firmware bug where querying LED intensity (`ia`, `ib`, etc.) accidentally enables the channel.

**Evidence:**
- V1.1 firmware introduced `get_led_intensity()` - might have bug
- Calibration worked fine in V1.0 (no LED queries)

**Test:** Compare V1.0 vs V1.1 firmware behavior

---

## Test Script Created

**File:** `test_led_commands.py`

### Purpose
Validate LED command behavior during calibration Steps 1-2 to identify root cause.

### Test Cases

#### Test 1: LED Off Verification
- Turn off all LEDs via `turn_off_channels()`
- Query LED state up to 5 times
- Verify all LEDs report intensity=0
- **Checks:** Does LED query command cause LEDs to turn on?

#### Test 2: LED Command Sequence
- Start with all LEDs off
- Query LED state (should remain off)
- Turn on single channel (Channel A)
- Verify only Channel A is on
- **Checks:** Does turn_on_channel() affect other channels?

#### Test 3: Batch LED Command (V1.1+ Only)
- Test batch command with all LEDs at 0
- Test batch command with one LED at 50
- Verify LED state matches expected
- **Checks:** Does batch command work correctly?

#### Test 4: set_intensity(ch, 0)
- Set channel A to 100
- Set channel A to 0
- Verify channel A is disabled
- **Checks:** Does set_intensity(0) properly disable channel?

---

## Running the Test

### Command
```powershell
.venv312\Scripts\python.exe test_led_commands.py
```

### Configuration
Edit `TEST_CONTROLLER_TYPE` in script:
- `"pico"` for PicoP4SPR
- `"arduino"` for ArduinoP4SPR

### Expected Output
```
================================================================================
LED COMMAND TEST SUITE
Testing calibration Step 1-2 LED behavior
================================================================================

Initializing PicoP4SPR controller...
✅ Controller connected: PicoP4SPR V1.1
   Firmware version: V1.1

================================================================================
TEST 1: LED OFF VERIFICATION (Step 1 of Calibration)
================================================================================

1. Turning off all LEDs...
   Result: ✅ SUCCESS

2. LED query available: True

3. Verifying LED state (V1.1+ firmware)...
   Attempt 1/5: {'a': 0, 'b': 0, 'c': 0, 'd': 0}
   ✅ All LEDs confirmed OFF

[... more tests ...]

✅ ALL TESTS COMPLETE
```

### What to Observe
1. **Do any LEDs physically turn on during the test?**
   - If YES → Firmware bug or communication issue
   - If NO → Problem is elsewhere in calibration flow

2. **Do LED queries return correct values?**
   - If NO → Firmware query commands might be broken

3. **Does batch command work (V1.1+)?**
   - If NO → Use sequential commands instead

---

## Recommended Actions

### Immediate
1. **Run `test_led_commands.py`** with hardware connected
2. **Observe physical LEDs** - note when they turn on
3. **Compare test output** to expected behavior
4. **Document findings** - which test causes LEDs to activate?

### If LEDs Turn On During Test
- **Root cause:** Firmware bug in LED query or turn_off_channels
- **Solution:**
  1. Downgrade to V1.0 firmware (if available)
  2. Report bug to firmware developer
  3. Use timing-based approach (disable LED queries)

### If LEDs Stay Off During Test
- **Root cause:** Problem is in calibration Step 3+ (LED ranking)
- **Solution:** Investigate Step 3 LED brightness ranking code

---

## Code Locations Summary

### Calibration Flow
- **Step 1 (Hardware Validation):** `calibration_6step.py` lines 586-651
- **Step 2 (Wavelength Calibration):** `calibration_6step.py` lines 653-704

### Controller Methods
- **turn_off_channels():** `controller.py` line 1027
- **turn_on_channel():** `controller.py` line 895
- **get_all_led_intensities():** `controller.py` line 964
- **set_intensity():** `controller.py` line 1044

### Test Script
- **test_led_commands.py:** Root directory

---

## Firmware Commands Reference

| Command | Description | Expected Response |
|---------|-------------|------------------|
| `lx\n` | Disable all LED channels | `1` |
| `la\n` | Enable LED A | `1` |
| `lb\n` | Enable LED B | `1` |
| `lc\n` | Enable LED C | `1` |
| `ld\n` | Enable LED D | `1` |
| `ia\n` | Query LED A intensity | `000` to `255` |
| `ib\n` | Query LED B intensity | `000` to `255` |
| `ic\n` | Query LED C intensity | `000` to `255` |
| `id\n` | Query LED D intensity | `000` to `255` |
| `ba128\n` | Set LED A to 128 | `1` |
| `batch:255,128,64,0\n` | Set all LEDs (V1.1+) | `1` |

---

## Next Steps

1. ✅ Run `test_led_commands.py` test script
2. ⏳ Document which test causes LEDs to activate
3. ⏳ Analyze serial communication with logic analyzer (if needed)
4. ⏳ Implement fix based on root cause:
   - Option A: Fix firmware bug
   - Option B: Modify Python code to avoid triggering bug
   - Option C: Use workaround (disable LED queries, use timing)

---

## Conclusion

The LED activation issue likely stems from one of:
1. Firmware bug in LED query commands (V1.1+)
2. `turn_off_channels()` not fully disabling LEDs
3. Timing issue with LED decay

The test script will definitively identify the root cause by isolating each LED command and observing physical LED behavior.

**Run the test and report back with results!**
