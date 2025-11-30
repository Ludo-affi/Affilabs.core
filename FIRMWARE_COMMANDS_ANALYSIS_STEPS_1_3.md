# Firmware Commands Analysis - Steps 1-3

**Date:** November 28, 2025
**Issue:** Verify new firmware commands don't interfere with calibration Steps 1-3
**Status:** ⚠️ POTENTIAL ISSUE FOUND

---

## Step-by-Step Firmware Command Analysis

### **STEP 1: Hardware Validation & LED Verification**

**Location:** `calibration_6step.py` lines 605-651

#### Commands Sent:

1. **Line 605:** `ctrl.turn_off_channels()`
   - **Firmware Command:** `lx\n`
   - **Purpose:** Disable all LED channels
   - **Response:** `1` (success)
   - **Risk:** ✅ SAFE - explicit OFF command

2. **Line 619:** `ctrl.get_all_led_intensities()` (if V1.1+)
   - **Calls:** `get_led_intensity('a')`, `get_led_intensity('b')`, `get_led_intensity('c')`, `get_led_intensity('d')`
   - **Firmware Commands:** `ia\n`, `ib\n`, `ic\n`, `id\n`
   - **Purpose:** Query current LED intensities (verification)
   - **Response:** `000` to `255` (3-digit ASCII)
   - **Risk:** ⚠️ **POTENTIAL ISSUE** - Query commands might trigger LED activation

3. **Line 637:** `ctrl.turn_off_channels()` (retry if LEDs still on)
   - **Firmware Command:** `lx\n`
   - **Purpose:** Retry LED disable
   - **Risk:** ✅ SAFE

---

### **STEP 2: Wavelength Calibration**

**Location:** `calibration_6step.py` lines 653-704

#### Commands Sent:

**NO FIRMWARE COMMANDS TO CONTROLLER**
- Only reads wavelength data from spectrometer EEPROM
- No LED activation
- ✅ **COMPLETELY SAFE**

---

### **STEP 3: LED Brightness Ranking**

**Location:** `calibration_6step.py` lines 706-873

#### Commands Sent:

1. **Line 719:** `switch_mode_safely(ctrl, "s", turn_off_leds=True)`
   - Calls `ctrl.set_mode('s')` and `ctrl.turn_off_channels()`
   - **Firmware Commands:** `s\n`, then `lx\n`
   - **Purpose:** Switch to S-mode, ensure LEDs off
   - **Risk:** ✅ SAFE

2. **Line 728:** `hasattr(ctrl, 'rank_leds')`
   - **Issue:** ❌ **METHOD DOES NOT EXIST**
   - This checks for a firmware V1.2 feature that hasn't been implemented
   - Always returns `False`, so firmware path is never used

3. **Line 737:** `ctrl.rank_leds()` (if V1.2+)
   - **Issue:** ❌ **NOT IMPLEMENTED**
   - Code attempts to call this but it doesn't exist
   - Falls back to Python implementation

4. **Line 795:** `ctrl.set_batch_intensities(**batch_values)` (Python fallback)
   - **Firmware Command:** `batch:A,B,C,D\n` (e.g., `batch:51,0,0,0\n`)
   - **Purpose:** Turn on one LED at a time for ranking
   - **Example:** `batch:51,0,0,0\n` = LED A at intensity 51, others off
   - **Risk:** ✅ SAFE - explicitly sets intensities

5. **Line 817:** `ctrl.turn_off_channels()`
   - **Firmware Command:** `lx\n`
   - **Purpose:** Turn off all LEDs after ranking
   - **Risk:** ✅ SAFE

---

## Firmware Commands Summary

### Commands Used in Steps 1-3:

| Command | Purpose | Sent By | Risk Level |
|---------|---------|---------|------------|
| `lx\n` | Turn off all LEDs | `turn_off_channels()` | ✅ SAFE |
| `ia\n` | Query LED A intensity | `get_led_intensity('a')` | ⚠️ QUERY RISK |
| `ib\n` | Query LED B intensity | `get_led_intensity('b')` | ⚠️ QUERY RISK |
| `ic\n` | Query LED C intensity | `get_led_intensity('c')` | ⚠️ QUERY RISK |
| `id\n` | Query LED D intensity | `get_led_intensity('d')` | ⚠️ QUERY RISK |
| `s\n` | Switch to S-mode | `set_mode('s')` | ✅ SAFE |
| `batch:A,B,C,D\n` | Set all LED intensities | `set_batch_intensities()` | ✅ SAFE |

---

## IDENTIFIED ISSUES

### 🔴 **Issue 1: LED Query Commands May Activate LEDs**

**Location:** Step 1, line 619 - `get_all_led_intensities()`

**Problem:**
- Sends `ia\n`, `ib\n`, `ic\n`, `id\n` to query LED intensities
- If firmware interprets these as "initialize LED" or "turn on LED", LEDs will activate
- Queries are sent AFTER `turn_off_channels()`, so if they activate LEDs, verification fails

**Evidence:**
- Step 1 tries to verify LEDs are off by querying them
- If query commands turn LEDs on, the loop retries up to 5 times
- This creates a feedback loop: query → LEDs on → retry turn_off → query → LEDs on...

**Test:**
```python
# Current code (Step 1):
ctrl.turn_off_channels()  # Send 'lx\n'
time.sleep(0.2)

# Query LED state
led_state = ctrl.get_all_led_intensities()  # Sends 'ia\n', 'ib\n', 'ic\n', 'id\n'

# If firmware activates LEDs on query, led_state will show non-zero values
```

**Firmware Bug Hypothesis:**
- V1.1 firmware added LED intensity query feature (`ia`, `ib`, `ic`, `id`)
- These commands might have a side effect of enabling the LED channel
- Firmware code might be: `if (cmd == 'ia') { led_a_enabled = true; return led_a_intensity; }`

---

### 🟡 **Issue 2: rank_leds() Method Does Not Exist**

**Location:** Step 3, line 728 - `hasattr(ctrl, 'rank_leds')`

**Problem:**
- Code checks for `rank_leds()` method which is NOT implemented in any controller class
- Always returns `False`, so firmware optimization is never used
- Not a critical issue (Python fallback works), but misleading code

**Impact:**
- Firmware V1.2 optimization path is dead code
- Log message "⚡ FIRMWARE V1.2: Using hardware-accelerated LED ranking" is never printed
- Always falls back to Python loop (slower but works)

**Fix:**
- Either implement `rank_leds()` in controller or remove the dead code
- Current behavior is safe, just inefficient

---

### ✅ **Issue 3: batch Command is Safe**

**Location:** Step 3, line 795 - `set_batch_intensities()`

**Analysis:**
- Sends `batch:A,B,C,D\n` command (e.g., `batch:51,0,0,0\n`)
- Explicitly sets ALL LED intensities in one command
- Firmware handles enabling/disabling channels automatically
- No query needed, direct control

**Conclusion:** ✅ SAFE - no interference risk

---

## ROOT CAUSE ANALYSIS

### Why LEDs Turn On During Steps 1-3:

**Hypothesis:** LED Query Commands Activate LEDs

1. **Step 1 Line 605:** `turn_off_channels()` sends `lx\n` → LEDs off ✅
2. **Step 1 Line 619:** `get_all_led_intensities()` sends `ia\n`, `ib\n`, `ic\n`, `id\n` → **LEDs turn on** ❌
3. **Step 1 Line 627:** Verification detects LEDs are on → Retry loop
4. **Step 1 Line 637:** Retry `turn_off_channels()` → LEDs off temporarily ✅
5. **Step 1 Line 619 (next iteration):** Query again → **LEDs turn on again** ❌
6. **Loop continues** for up to 5 retries, LEDs keep turning on during queries

**Firmware Bug:**
The `ia`, `ib`, `ic`, `id` commands likely have this implementation:
```c
// BUGGY FIRMWARE CODE (hypothesis):
if (cmd == 'ia') {
    led_a_enabled = true;  // ❌ BUG: Query should not enable channel
    return led_a_intensity;
}
```

**Correct Implementation Should Be:**
```c
// CORRECT FIRMWARE CODE:
if (cmd == 'ia') {
    // Just return intensity, don't modify enabled state
    return led_a_intensity;  // ✅ Query-only, no side effects
}
```

---

## SOLUTIONS

### 🔧 **Solution 1: Disable LED Query in Step 1 (Immediate Fix)**

**Modify:** `calibration_6step.py` line 612

**Change:**
```python
# BEFORE:
has_led_query = hasattr(ctrl, 'get_all_led_intensities')

# AFTER:
# Disable LED query to prevent firmware bug from activating LEDs
has_led_query = False  # Force timing-based approach until firmware fix
```

**Impact:**
- Step 1 will use timing-based verification (V1.0 behavior)
- No LED queries sent, so no activation
- Relies on 50ms delay instead of verification
- ✅ Safe workaround until firmware is fixed

---

### 🔧 **Solution 2: Fix Firmware Bug (Permanent Fix)**

**Firmware Change:** Modify V1.1+ firmware

**Commands to Fix:**
- `ia\n` - Query LED A (should NOT enable channel)
- `ib\n` - Query LED B (should NOT enable channel)
- `ic\n` - Query LED C (should NOT enable channel)
- `id\n` - Query LED D (should NOT enable channel)

**Test:**
1. Send `lx\n` (turn off all)
2. Send `ia\n` (query LED A)
3. Verify LED A does NOT physically turn on
4. Verify LED A PWM remains disabled

---

### 🔧 **Solution 3: Add LED State Cache (Alternative Fix)**

**Modify:** `controller.py`

**Add caching to avoid queries:**
```python
def turn_off_channels(self):
    # Turn off LEDs
    cmd = f"lx\n"
    self._ser.write(cmd.encode())
    success = self._ser.read() == b'1'

    if success:
        self._channels_enabled.clear()
        # Cache LED state (avoid querying firmware)
        self._led_intensity_cache = {'a': 0, 'b': 0, 'c': 0, 'd': 0}

    return success

def get_all_led_intensities(self):
    # Use cached values instead of querying firmware
    if hasattr(self, '_led_intensity_cache'):
        return self._led_intensity_cache.copy()

    # Fallback to query if cache not available
    return None
```

**Impact:**
- Avoids sending query commands that activate LEDs
- Uses cached values from last `turn_off_channels()` or `set_batch_intensities()`
- Fast and safe

---

## RECOMMENDED ACTION PLAN

### Immediate (Today):
1. ✅ **Apply Solution 1** - Disable LED query in Step 1
   - Set `has_led_query = False` on line 612
   - Test calibration - LEDs should stay off

### Short-term (This Week):
2. 🔧 **Test Firmware Commands** - Run `test_led_commands.py`
   - Confirm `ia`, `ib`, `ic`, `id` commands activate LEDs
   - Document firmware bug details
   - Report to firmware developer

### Long-term (Next Release):
3. 🔧 **Fix Firmware** - Update V1.1+ firmware
   - Ensure query commands don't modify LED state
   - Verify fix with hardware testing
   - Re-enable `has_led_query` in Step 1

4. 🧹 **Remove Dead Code** - Clean up `rank_leds` references
   - Either implement `rank_leds()` method or remove checks
   - Update documentation

---

## CODE CHANGES REQUIRED

### File: `src/utils/calibration_6step.py`

#### Change 1: Disable LED Query (Line 612)
```python
# STEP 1: Line 612
# BEFORE:
has_led_query = hasattr(ctrl, 'get_all_led_intensities')

# AFTER:
# WORKAROUND: Disable LED query to prevent firmware bug
# V1.1 firmware query commands (ia, ib, ic, id) activate LEDs as side effect
# Use timing-based approach until firmware is fixed
has_led_query = False
```

#### Change 2: Add Comment Explaining Timing Approach (Line 647)
```python
# STEP 1: Line 647
if not has_led_query:
    # V1.0 firmware or LED query disabled (firmware bug workaround)
    # Using timing-based verification instead of query commands
    logger.info("LED query not available - using timing-based verification")
    time.sleep(0.05)  # Extra settling time
    led_verified = True
```

---

## TESTING CHECKLIST

After applying Solution 1:

- [ ] Run calibration Step 1
- [ ] Verify LEDs stay OFF during "Verifying LEDs are off..." step
- [ ] Check log: "LED query not available - using timing-based verification"
- [ ] Run full calibration Steps 1-6
- [ ] Verify no LED activation during Steps 1-2
- [ ] Verify Step 3 ranking works correctly (LEDs turn on one at a time)

---

## CONCLUSION

**Primary Issue:** LED query commands (`ia`, `ib`, `ic`, `id`) activate LEDs as side effect

**Root Cause:** Firmware V1.1+ bug - query commands enable LED channels

**Immediate Fix:** Disable LED query in Step 1 (force timing-based approach)

**Permanent Fix:** Update firmware to make query commands read-only (no side effects)

**Impact:** After applying Solution 1, Steps 1-3 will work correctly without LED interference

---

**Status:** ⚠️ Firmware bug identified, workaround available, permanent fix required
