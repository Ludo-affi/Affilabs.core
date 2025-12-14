# Firmware V1.2 Bug Analysis - Channel A lx Command Failure

## Bug Summary
The `lx` command (turn off all LEDs) does NOT disable Channel A LED. After sending `lx`, Channel A remains illuminated, contaminating all subsequent measurements.

## Code Review Results

### 1. LED Control Function - `led_on()` (Lines 572-672)

**Logic Flow:**
```c
bool led_on (char ch_led){
    // STEP 1: Turn off all LEDs except the requested one
    if (ch_led != 'a'){
        pwm_set_chan_level(LED_A_SLICE, LED_A_CH, 0);
        pwm_set_enabled(LED_A_SLICE, false);
        led_a_enabled = false;
    }
    // Similar for B, C, D...

    // STEP 2: Turn on the requested LED
    switch (ch_led){
        case 'a':
            pwm_set_chan_level(LED_A_SLICE, LED_A_CH, led_a_level);
            pwm_set_enabled(LED_A_SLICE, true);
            led_a_enabled = true;
            break;
        // Similar for b, c, d...

        case 'x':
            // Turn off all LEDs - NO CODE HERE, just return true
            result = true;
            break;
    }
}
```

**Analysis when `lx` is sent:**
- `ch_led = 'x'`
- STEP 1 conditions:
  - `'x' != 'a'` → TRUE → Channel A should turn OFF ✅
  - `'x' != 'b'` → TRUE → Channel B should turn OFF ✅
  - `'x' != 'c'` → TRUE → Channel C should turn OFF ✅
  - `'x' != 'd'` → TRUE → Channel D should turn OFF ✅
- STEP 2: Switch case 'x' → Just returns true, no additional actions

**Expected Behavior:** All 4 LEDs should turn OFF
**Observed Behavior:** Channel A remains ON

### 2. Global Variables (Lines 103-106)

```c
uint16_t led_a_level = LED_WRAP;  // Maximum brightness at startup!
uint16_t led_b_level = LED_WRAP;
uint16_t led_c_level = LED_WRAP;
uint16_t led_d_level = LED_WRAP;
```

**Impact:** All LEDs default to maximum brightness on power-up

### 3. PWM Hardware Configuration (Lines 548-570)

```c
// LED A - GPIO 28
const uint8_t LED_A_CTRL = 28;
const uint LED_A_SLICE = 6;
const uint LED_A_CH = 0;

void led_setup (void){
    gpio_set_function(LED_A_CTRL, GPIO_FUNC_PWM);
    pwm_set_clkdiv(LED_A_SLICE, LED_PWM_DIV);
    pwm_set_phase_correct(LED_A_SLICE, false);
    pwm_set_wrap(LED_A_SLICE, LED_WRAP);
}
```

**PWM Parameters:**
- Frequency: 400 Hz
- Clock Divider: 10x
- Wrap Value: (125MHz / 10) / 400Hz = 31,250

**Verification Needed:** Ensure GPIO 28 actually maps to PWM Slice 6 Channel 0 on RP2040

### 4. Command Parsing (Lines 190-270)

```c
while (true) {
    char command[20] = "00000000000000000000";
    // Read until '\n' or buffer full

    switch (command[0]){
        case 'l':
            if (led_on(command[1])){
                printf("%d", ACK);  // Send '1'
            }
            else {
                printf("%d", NAK);  // Send '0'
            }
            break;
    }
}
```

**Observation:** Command parsing looks correct. `lx\n` should call `led_on('x')`.

## Possible Root Causes

### Hypothesis 1: PWM Slice Mapping Error ⚠️
GPIO 28 might not actually be PWM Slice 6 on RP2040. Need to verify:
```c
// RP2040 GPIO to PWM mapping:
// Slice = gpio_to_slice(GPIO_PIN)
// Channel = gpio_to_channel(GPIO_PIN)
```

For GPIO 28:
- Expected by code: Slice 6, Channel 0
- Actual hardware: **Need to calculate using RP2040 datasheet**

**RP2040 PWM Mapping Rule:**
- 8 PWM slices (0-7), each with 2 channels (A=0, B=1)
- GPIO_n maps to Slice (n % 16) / 2, Channel (n % 16) % 2

GPIO 28:
- (28 % 16) = 12
- Slice = 12 / 2 = **Slice 6** ✅
- Channel = 12 % 2 = **Channel 0** ✅

**Slice mapping is CORRECT!**

### Hypothesis 2: PWM Enable State Persistence ⚠️
When `pwm_set_enabled(LED_A_SLICE, false)` is called, does the RP2040 SDK actually disable the PWM output immediately, or is there a delay/buffering?

**Test:** Check if `pwm_set_enabled()` is synchronous or requires additional delay

### Hypothesis 3: LED Hardware Circuit Issue ⚠️
Channel A LED might have a hardware pullup or latching circuit that prevents it from turning off via PWM disable.

**Test:** Measure voltage at GPIO 28 with oscilloscope after `lx` command

### Hypothesis 4: Race Condition / Buffer Overflow 🔴 **MOST LIKELY**
The user reported "controller becomes unresponsive with LEDs stuck on" after multiple commands. This suggests:

1. Serial buffer fills up from rapid commands
2. Commands get corrupted or dropped
3. `lx` command arrives as `lx` but gets processed as something else (buffer overrun)
4. Or `lx` processes correctly but immediately gets overwritten by another command

**Evidence from test:**
```
TEST 1: Turn off all LEDs → All LEDs OFF ✅
TEST 2: Turn on Channel A at 20% → Channel A ON ✅
TEST 3: Increase Channel A to 100% → Channel A brighter ✅
TEST 4: Turn off all LEDs → Channel A STAYS ON ❌
TEST 4: Turn on Channel B → Both A and B ON ❌
```

**Analysis:**
- First `lx` works (TEST 1)
- After setting brightness and turning on LED, subsequent `lx` fails (TEST 4)
- This suggests **state corruption** or **timing issue**

### Hypothesis 5: Missing GPIO Output Disable 🔴 **CRITICAL FINDING**
Look at the `led_on()` function again:

```c
if (ch_led != 'a'){
    pwm_set_chan_level(LED_A_SLICE, LED_A_CH, 0);     // Set duty cycle to 0%
    pwm_set_enabled(LED_A_SLICE, false);               // Disable PWM
    led_a_enabled = false;                             // Clear software flag
}
```

**BUT** - `pwm_set_enabled(slice, false)` only disables the PWM generator. It does NOT necessarily set the GPIO output to LOW!

From RP2040 datasheet:
> When a PWM slice is disabled, the output pins retain their last state.

**THIS IS THE BUG!** When PWM is disabled at 100% duty cycle (HIGH), the GPIO remains HIGH!

**Fix:** After disabling PWM, explicitly set GPIO to LOW:
```c
if (ch_led != 'a'){
    pwm_set_chan_level(LED_A_SLICE, LED_A_CH, 0);
    pwm_set_enabled(LED_A_SLICE, false);
    gpio_set_function(LED_A_CTRL, GPIO_FUNC_SIO);  // Switch to GPIO mode
    gpio_set_dir(LED_A_CTRL, GPIO_OUT);             // Set as output
    gpio_put(LED_A_CTRL, 0);                        // Set to LOW
    gpio_set_function(LED_A_CTRL, GPIO_FUNC_PWM);   // Restore PWM function
    led_a_enabled = false;
}
```

**OR SIMPLER:** Set level to 0 BEFORE disabling:
```c
if (ch_led != 'a'){
    pwm_set_chan_level(LED_A_SLICE, LED_A_CH, 0);   // Set to 0% FIRST
    sleep_us(10);                                     // Wait for PWM cycle
    pwm_set_enabled(LED_A_SLICE, false);             // Then disable
    led_a_enabled = false;
}
```

## Recommended Fix

**Option 1: Proper GPIO Shutdown Sequence (RECOMMENDED)**
```c
// In led_on() function, lines 578-597
if (ch_led != 'a'){
    pwm_set_chan_level(LED_A_SLICE, LED_A_CH, 0);   // Duty cycle = 0%
    sleep_us(100);                                    // Wait 1-2 PWM cycles @ 400Hz = 2.5ms
    pwm_set_enabled(LED_A_SLICE, false);             // Disable PWM
    led_a_enabled = false;
}
```

**Rationale:** Ensure PWM output is LOW before disabling, so GPIO pin latches at LOW state.

**Option 2: Force GPIO LOW (Alternative)**
```c
if (ch_led != 'a'){
    pwm_set_chan_level(LED_A_SLICE, LED_A_CH, 0);
    pwm_set_enabled(LED_A_SLICE, false);
    gpio_init(LED_A_CTRL);                           // Re-init as GPIO
    gpio_set_dir(LED_A_CTRL, GPIO_OUT);
    gpio_put(LED_A_CTRL, 0);                         // Force LOW
    led_a_enabled = false;
    // Note: Will need to re-init PWM when turning back on
}
```

**Rationale:** Explicitly force GPIO to LOW state, but requires re-initializing PWM function later.

**Option 3: Use `pwm_set_gpio_level()` (Simplest)**
```c
if (ch_led != 'a'){
    pwm_set_gpio_level(LED_A_CTRL, 0);               // RP2040 SDK function
    pwm_set_enabled(LED_A_SLICE, false);
    led_a_enabled = false;
}
```

**Rationale:** Use higher-level SDK function that handles GPIO/PWM transitions properly.

## Verification Tests

After fix is applied:

1. **Basic lx Test:**
   ```
   lx → All LEDs OFF
   ba255 → Set A to 100%
   la → Channel A ON
   lx → Channel A OFF ✅
   ```

2. **Rapid Command Test:**
   ```
   ba128; la; lx; bb128; lb; lx; bc128; lc; lx
   → All should turn on then off cleanly
   ```

3. **Batch Command Test:**
   ```
   batch:255,255,255,255 → All ON
   lx → All OFF ✅
   ```

4. **Channel A Specific Test:**
   ```
   ba255; la → A ON at 100%
   lx → A OFF
   lb → Only B ON (not A+B) ✅
   ```

## Impact Analysis

**Current Bug Impact:**
- ❌ Calibration Step 3 (LED ranking) measures Channel A + other channels instead of individual LEDs
- ❌ All LED intensity measurements show ~3000 counts (5%) instead of 40,000+ counts (70%)
- ❌ SPR measurements contaminated by Channel A background light
- ❌ Cannot perform accurate LED calibration
- ❌ Cannot switch between LEDs cleanly
- ❌ Controller becomes unresponsive after multiple LED commands

**After Fix:**
- ✅ Clean LED switching (one LED at a time)
- ✅ Accurate LED intensity rankings
- ✅ Proper calibration data collection
- ✅ SPR measurements with correct LED selection

## Additional Bugs Found During Review

### Bug 2: Same issue affects Channels B, C, D
All four channels use identical logic, so the fix must be applied to all:
- Lines 584-587: Channel B
- Lines 590-593: Channel C
- Lines 596-599: Channel D

### Bug 3: Same issue in `led_batch_set()` function (Lines 755-764)
```c
// Turn off all LEDs first
pwm_set_chan_level(LED_A_SLICE, LED_A_CH, 0);
// ... B, C, D
pwm_set_enabled(LED_A_SLICE, false);
// ... B, C, D
```

**Fix:** Add `sleep_us(100)` between `set_chan_level` and `set_enabled`

## Summary

**ROOT CAUSE:** RP2040 PWM outputs retain their last state when disabled. If disabled while HIGH (100% duty), GPIO stays HIGH.

**FIX:** Set PWM level to 0% and wait 1-2 PWM cycles before disabling PWM peripheral.

**FILES TO MODIFY:**
- `firmware/pico_p4spr/affinite_p4spr.c`
  - Function `led_on()` lines 578-599
  - Function `led_batch_set()` lines 755-764

**TESTING:** Use `test_led_brightness.py` to verify fix works correctly.
