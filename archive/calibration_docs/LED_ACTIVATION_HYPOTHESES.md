# Alternative Hypotheses: Why All LEDs Turn On (Steps 1-3)

**Date:** November 28, 2025
**Status:** Firmware query validated safe - investigating other causes
**Validation:** Query commands (`ia`, `ib`, `ic`, `id`) confirmed READ-ONLY ✅

---

## Confirmed Facts

1. ✅ **Firmware query commands are safe** - No side effects (validated 2025-11-28)
2. ✅ **Step 1:** Explicitly turns off LEDs via `lx` command
3. ✅ **Step 2:** NO LED commands sent (only wavelength EEPROM read)
4. ✅ **Step 3:** Intentionally turns on LEDs one at a time for ranking

---

## Hypothesis 1: User Is Observing Step 3 (Expected Behavior)

### Evidence
**Step 3 Line 721:** `switch_mode_safely(ctrl, "s", turn_off_leds=True)`
**Step 3 Line 795:** `ctrl.set_batch_intensities(**batch_values)` - Turns on LEDs one at a time

### Step 3 Normal Operation:
```python
# Line 790-800: Python fallback LED ranking
for ch in ch_list:  # Iterate: 'a', 'b', 'c', 'd'
    # Turn on ONLY this channel
    batch_values = {c: (test_led_intensity if c == ch else 0) for c in ['a', 'b', 'c', 'd']}
    ctrl.set_batch_intensities(**batch_values)  # e.g., batch:51,0,0,0
    time.sleep(LED_DELAY)

    # Read spectrum with this LED on
    raw_spectrum = usb.read_spectrum()

    # Analysis...

# Turn off all LEDs after ranking
ctrl.turn_off_channels()
```

### Timeline:
1. **Step 1 (0-5s):** LEDs off, verify off → ✅ LEDs should be OFF
2. **Step 2 (5-7s):** Read wavelengths → ✅ LEDs should be OFF
3. **Step 3 Start (7-10s):** Switch mode, LEDs off → ✅ LEDs should be OFF
4. **Step 3 Ranking (10-15s):** → ⚠️ **LEDs turn on ONE AT A TIME** (EXPECTED)
   - LED A on at 51 (20%) for ~100ms
   - LED B on at 51 (20%) for ~100ms
   - LED C on at 51 (20%) for ~100ms
   - LED D on at 51 (20%) for ~100ms

### Probability: ⭐⭐⭐⭐⭐ **VERY HIGH**

**Reason:** Step 3 intentionally activates LEDs. If user is watching during Step 3, seeing all LEDs light up sequentially is **NORMAL BEHAVIOR**.

**Test:** Add log timestamps and note exactly when LEDs turn on.

---

## Hypothesis 2: set_mode() Command Side Effect

### Evidence
**Step 3 Line 721:** `switch_mode_safely(ctrl, "s", turn_off_leds=True)`

This calls:
1. `ctrl.turn_off_channels()` → Sends `lx\n`
2. `ctrl.set_mode("s")` → Sends `ss\n` (switch to S-mode)

### Firmware Command: `ss\n` (PicoP4SPR)

**Location:** `controller.py` line 1296-1308

```python
def set_mode(self, mode='s'):
    if mode == 's':
        cmd = f"ss\n"  # Switch to S-mode
    else:
        cmd = f"sp\n"  # Switch to P-mode
    self._ser.write(cmd.encode())
    return self._ser.read() == b'1'
```

### Potential Bug:
Firmware `ss` or `sp` command might:
- Move servo to S/P position ✅ Expected
- **Enable all LED channels as side effect** ❌ Bug
- **Turn on LEDs at last intensity** ❌ Bug

### How to Test:
```python
# Test script
ctrl.turn_off_channels()  # LEDs off
time.sleep(1.0)
# OBSERVE: LEDs should be OFF

ctrl.set_mode('s')  # Just switch mode
time.sleep(1.0)
# OBSERVE: Do LEDs turn on?

ctrl.set_mode('p')  # Switch to P
time.sleep(1.0)
# OBSERVE: Do LEDs turn on?
```

### Probability: ⭐⭐⭐ **MODERATE**

**Reason:** Mode switch involves servo movement, firmware might inadvertently enable LED channels.

---

## Hypothesis 3: Batch Command With Zero Values Enables Channels

### Evidence
**Step 3 Line 721:** `switch_mode_safely()` with `turn_off_leds=True`

This eventually verifies with:
```python
verify_hardware_state(ctrl, expected_leds={'a': 0, 'b': 0, 'c': 0, 'd': 0})
```

### Potential Issue:
The verification might use `set_batch_intensities(a=0, b=0, c=0, d=0)` somewhere, which could:
- Set intensity to 0 ✅ Expected
- **Enable all channels at 0%** ❌ Bug (channels enabled but PWM = 0)
- **Channels briefly flash on before PWM updates** ❌ Bug

### Firmware Command: `batch:0,0,0,0\n`

**Expected behavior:**
- All LEDs off (intensity = 0)

**Buggy behavior:**
- Enables all 4 channels
- Brief flash before PWM settles to 0
- Or residual light due to electrical characteristics

### How to Test:
```python
ctrl.turn_off_channels()  # Use lx command
time.sleep(1.0)
# OBSERVE: LEDs off

ctrl.set_batch_intensities(a=0, b=0, c=0, d=0)  # Batch with zeros
time.sleep(0.5)
# OBSERVE: Do LEDs flash or turn on?
```

### Probability: ⭐⭐ **LOW**

**Reason:** Batch command is well-tested, unlikely to enable channels at 0 intensity.

---

## Hypothesis 4: Hardware Electrical Behavior

### Evidence
LEDs are physical devices with electrical characteristics:
- **Capacitive coupling** - Adjacent LED traces can couple
- **Residual charge** - Capacitors in LED driver circuit
- **Ghosting** - Weak current paths when "off"
- **Afterglow** - LED phosphor continues emitting after current stops

### Potential Causes:

#### A. Servo Movement Generates Electrical Noise
- Servo motor draws high current (~500mA surge)
- Current spike causes voltage droop on shared power rail
- LED drivers briefly activate during voltage sag
- LEDs flash for 1-10ms

#### B. Shared Ground Impedance
- LEDs and servo share common ground
- Servo current causes ground bounce
- LED drivers see false "enable" signal
- Brief LED activation

#### C. PWM Bleed-Through
- LED PWM signals capacitively couple to other channels
- When one LED is on, others show weak ghosting
- Appears as "all LEDs on" but actually dim ghosting

### How to Test:
1. **Disconnect servo** - Run calibration with servo unplugged
2. **Measure with scope** - Check LED driver signals during mode switch
3. **Current probe** - Measure servo current during switch
4. **Vary timing** - Increase delays and observe if issue persists

### Probability: ⭐⭐⭐ **MODERATE**

**Reason:** Servo movement happens during Step 3 (`set_mode('s')`), timing matches LED activation.

---

## Hypothesis 5: Firmware State Machine Bug

### Evidence
Firmware V1.2 might have state machine that:
1. Receives `lx\n` → Disables all channels ✅
2. Receives `ss\n` → Moves servo to S position ✅
3. **State transition bug** → Restores previous LED state ❌

### Potential Bug Logic:
```c
// BUGGY FIRMWARE STATE MACHINE
void handle_set_mode(char mode) {
    move_servo(mode);

    // BUG: Restore LED state from before last mode switch
    restore_led_state();  // ❌ This re-enables LEDs!
}
```

### Expected Logic:
```c
// CORRECT FIRMWARE
void handle_set_mode(char mode) {
    move_servo(mode);
    // LEDs remain in current state (off if turned off)
    // No automatic restoration
}
```

### How to Test:
```python
# Sequence 1: Fresh start
ctrl.turn_off_channels()
ctrl.set_mode('s')
# OBSERVE: Do LEDs turn on?

# Sequence 2: With previous LED state
ctrl.set_batch_intensities(a=100, b=100, c=100, d=100)  # All on
time.sleep(1.0)
ctrl.turn_off_channels()  # Turn off
ctrl.set_mode('p')  # Switch mode
# OBSERVE: Do LEDs turn back on at 100?
```

### Probability: ⭐⭐⭐⭐ **HIGH**

**Reason:** Firmware state machines often save/restore state, could be restoring LED state on mode switch.

---

## Hypothesis 6: Integration Time Setting Triggers LEDs

### Evidence
**Step 3 Line 727:** `usb.set_integration(RANKING_INTEGRATION_TIME)`

This sets spectrometer integration time to 70ms.

### Potential Cross-Talk:
- Spectrometer and controller on same USB bus
- Integration time command causes USB traffic
- USB traffic triggers controller watchdog or reset
- Controller reset restores EEPROM LED values
- LEDs turn on at stored intensities

### How to Test:
```python
ctrl.turn_off_channels()
time.sleep(1.0)
# OBSERVE: LEDs off

usb.set_integration(0.070)  # Set integration time
time.sleep(0.5)
# OBSERVE: Do LEDs turn on?
```

### Probability: ⭐ **VERY LOW**

**Reason:** Spectrometer and controller are separate devices, no direct coupling expected.

---

## Hypothesis 7: Previous Session State

### Evidence
If calibration was run before and interrupted:
- LEDs might have been left on
- Firmware state persisted
- User thinks LEDs turn on during Steps 1-3
- Actually LEDs were already on from before

### Timeline:
1. **Previous session:** User stopped during Step 4 → LEDs left on
2. **Current session:** User starts calibration → LEDs already on
3. **Step 1:** `turn_off_channels()` → LEDs turn off briefly
4. **Step 3:** LEDs turn on for ranking → User sees this as "all LEDs on"

### How to Test:
- Unplug/replug controller USB before calibration
- Check LED state before starting calibration
- Add LED status check at calibration start

### Probability: ⭐⭐ **LOW**

**Reason:** Step 1 explicitly turns off LEDs and verifies, should clear previous state.

---

## Recommended Testing Sequence

### Test 1: Isolate Mode Switch Command
```python
# test_mode_switch.py
ctrl = PicoP4SPR()
ctrl.open()

print("1. Turn off all LEDs")
ctrl.turn_off_channels()
time.sleep(2.0)
input("OBSERVE: LEDs should be OFF. Press ENTER...")

print("2. Switch to S-mode (servo movement)")
ctrl.set_mode('s')
time.sleep(2.0)
input("OBSERVE: Did LEDs turn on after mode switch? (y/n): ")

print("3. Switch to P-mode")
ctrl.set_mode('p')
time.sleep(2.0)
input("OBSERVE: Did LEDs turn on after mode switch? (y/n): ")

ctrl.close()
```

### Test 2: Timing Analysis
```python
# Add timestamps to calibration logs
import time

start_time = time.time()

# In calibration_6step.py, add:
logger.info(f"[{time.time()-start_time:.2f}s] Step 1 start")
# ... existing code ...
logger.info(f"[{time.time()-start_time:.2f}s] LEDs turning off")
# ... etc ...
```

User notes exact timestamp when LEDs turn on → Correlate with log.

### Test 3: Firmware State Machine
```python
# Test if mode switch restores previous LED state
ctrl.set_batch_intensities(a=200, b=200, c=200, d=200)
time.sleep(1.0)
ctrl.turn_off_channels()
time.sleep(1.0)
# OBSERVE: LEDs off

ctrl.set_mode('s')
time.sleep(1.0)
# OBSERVE: Did LEDs turn back on at 200?
```

---

## Most Likely Causes (Ranked)

1. **⭐⭐⭐⭐⭐ Step 3 is expected** (User observing normal LED ranking)
2. **⭐⭐⭐⭐ Firmware state machine** (Mode switch restores LED state)
3. **⭐⭐⭐ Mode switch command** (`ss`/`sp` enables channels)
4. **⭐⭐⭐ Hardware electrical** (Servo noise couples to LEDs)
5. **⭐⭐ Previous session state** (LEDs left on from before)
6. **⭐⭐ Batch command zero bug** (Enables channels at 0%)
7. **⭐ Integration time cross-talk** (USB traffic triggers reset)

---

## Next Steps

1. **Run Test 1** - Isolate mode switch command
2. **Add timing logs** - Determine exact moment LEDs turn on
3. **Test firmware state machine** - Check if mode switch restores LEDs
4. **Review with user** - Confirm if observing Step 3 (expected) or Steps 1-2 (unexpected)

---

**Status:** Awaiting test results to determine root cause
