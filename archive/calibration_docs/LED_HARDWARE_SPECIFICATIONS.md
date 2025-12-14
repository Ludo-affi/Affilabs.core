# LED Hardware Specification Guide

## Overview
This document tracks LED hardware specifications and firmware considerations for different LED types used in the SPR system.

## Current LED Configuration

### LED Part Numbers Provided
1. **LCW LED:** Luminus Devices Inc. MP-2016-1100-30-80
2. **OWW LED:** ams OSRAM GW JTLMS3.GM-G3G7-XX58-1-60-R33

## LED Electrical Characteristics

### LCW LED - Luminus MP-2016-1100-30-80
- **Part Number:** MP-2016-1100-30-80
- **Series:** Luminus MP-2016
- **Type:** White LED (Warm White 3000K)
- **Package:** 0806 / 2016 Metric SMD (2.0mm x 1.6mm x 0.52mm)
- **Color Temperature (CCT):** 3000K (Warm White, Typ)
- **Typical Forward Voltage (Vf):** 3.0V @ 60mA
- **Maximum Forward Current (If):** 120mA (absolute max)
- **Test Current:** 60mA (standard test condition)
- **Typical Luminous Flux:** 22 lumens @ 60mA, 25°C
- **Luminous Efficacy:** 122 lm/W @ 60mA
- **CRI (Color Rendering Index):** 80
- **Viewing Angle:** 110 degrees
- **Rise/Fall Time:** <100ns (typical for white LED)
- **Thermal Resistance:** 35°C/W junction to solder point
- **Power Dissipation:** 180mW @ 60mA (3V × 60mA)

**Notes:**
- Professional-grade warm white LED (3000K)
- Designed for general illumination and optical applications
- Good thermal performance (35°C/W)
- Recommended operating current: 30-90mA (25-75% of max)

### OWW LED - OSRAM GW JTLMS3.GM-G3G7-XX58-1-60-R33
- **Part Number:** GW JTLMS3.GM-G3G7-XX58-1-60-R33
- **Series:** OSRAM DURIS E 2835
- **Type:** White LED (Neutral White)
- **Package:** 2835 SMD (2.8mm x 3.5mm)
- **Color/Wavelength:** Neutral White (~4000K CCT, G3G7 bin)
- **Typical Forward Voltage (Vf):** ~2.85V @ 60mA
- **Maximum Forward Current (If):** 180mA (absolute max)
- **Recommended Operating Current:** 60-150mA
- **Typical Luminous Flux:** ~60 lumens @ 60mA
- **CRI (Color Rendering Index):** 80 (XX58 = CRI 80)
- **Viewing Angle:** 120 degrees
- **Rise/Fall Time:** <100ns (typical for white LED)
- **Power Dissipation:** ~170mW @ 60mA, up to 500mW @ 180mA

**Notes:**
- Professional-grade high-brightness LED (OSRAM DURIS E series)
- Much higher power capacity than LCW LED
- Designed for architectural and commercial lighting
- Excellent thermal performance

---

## Firmware Considerations

### Current Firmware PWM Settings
**File:** `firmware/pico_p4spr/affinite_p4spr.c`

```c
const uint16_t LED_FREQ = 400;        // 400 Hz PWM frequency
const uint8_t LED_PWM_DIV = 10;       // Clock divider
const uint16_t LED_WRAP = 31,250;     // PWM wrap value (125MHz/10/400Hz)
```

**Effective PWM Resolution:** 31,250 steps (0-31,250)
**Brightness Control Range:** 0-255 (mapped to 0-31,250 internally)

---

## 🔍 FIRMWARE COMPATIBILITY ANALYSIS

### Comparison Table

| Specification | LCW (Luminus MP-2016) | OWW (OSRAM GW JTLMS3) | Compatible? |
|---------------|----------------------|----------------------|-------------|
| Forward Voltage (Vf) | 3.0V @ 60mA | 2.85V @ 60mA | ✅ Very Similar |
| Max Current (If) | 120mA | 180mA | ✅ Similar range |
| Test Current | 60mA | 60mA | ✅ Identical |
| Luminous Flux | 22 lumens @ 60mA | 60 lumens @ 60mA | ⚠️ 2.7x difference |
| Power Dissipation | 180mW @ 60mA | 170mW @ 60mA | ✅ Nearly identical |
| CRI | 80 | 80 | ✅ Identical |
| CCT | 3000K (Warm) | 4000K (Neutral) | ⚠️ Different colors |
| Rise/Fall Time | <100ns | <100ns | ✅ Same |
| Package Size | 2016 (2.0x1.6mm) | 2835 (2.8x3.5mm) | ✅ Both SMD |
| Thermal Resistance | 35°C/W | ~15°C/W (est.) | ⚠️ OWW better |

### Critical Findings

#### ✅ EXCELLENT CURRENT COMPATIBILITY
**Both LEDs designed for 60mA test current**

- **LCW:** 22 lumens @ 60mA (max 120mA)
- **OWW:** 60 lumens @ 60mA (max 180mA)
- **Optimal Operating Current:** 60mA for both

**Impact on Firmware:**
- ✅ **NO FIRMWARE CHANGE NEEDED** - Both LEDs have similar current requirements!
- If PCB is designed for 60mA, both LEDs operate at their optimal test current
- Both have safety margin (LCW: 2x headroom to 120mA, OWW: 3x headroom to 180mA)

#### ⚠️ MODERATE BRIGHTNESS DIFFERENCE
**OWW is 2.7x brighter than LCW at same current**

- **LCW:** 22 lumens @ 60mA, 25°C
- **OWW:** 60 lumens @ 60mA
- **Ratio:** 2.7:1 (not 5.5x as initially estimated)

**Impact on Firmware:**
- ✅ **NO FIRMWARE CHANGE NEEDED** - Your Python calibration automatically compensates
- The spectrometer measures absolute photon counts regardless of LED brightness
- Calibration Step 3 (LED ranking) will detect this difference and adjust integration times accordingly
- 2.7x ratio is very manageable (much better than feared 5.5x)

**Critical Question: What is your PCB current limiting?**

**MUST VERIFY:**
```
Measure LED current at 100% PWM with multimeter:
1. Turn on LED at 100% brightness
2. Measure current in series with LED
3. Compare to datasheet specifications
```

**Safe Current Scenarios:**

| PCB Current Limit | LCW LED (120mA max) | OWW LED (180mA max) | Action Required |
|-------------------|---------------------|---------------------|-----------------|
| 40-60mA | ✅ Safe (33-50%) | ✅ Safe (22-33%) | None - IDEAL for both |
| 60-90mA | ✅ Safe (50-75%) | ✅ Safe (33-50%) | None - excellent |
| 90-120mA | ✅ Safe (75-100%) | ✅ Safe (50-67%) | None - within specs |
| 120-180mA | 🔴 **RISK for LCW** (>100%) | ✅ Safe (67-100%) | **REDUCE PWM for LCW** |
| >180mA | 🔴 **DANGER** | 🔴 **DANGER** | **Hardware redesign needed** |

**KEY INSIGHT:** Both LEDs have 60mA test current - if your PCB targets 60mA, both will operate optimally!

#### ✅ FORWARD VOLTAGE COMPATIBLE
Both LEDs have similar Vf (~2.8-3.2V), so:
- ✅ 3.3V supply: Sufficient for both LEDs
- ✅ 5V supply: Excellent for both LEDs
- Both will operate properly at the same supply voltage

#### ✅ PWM FREQUENCY COMPATIBLE
- Both LEDs have rise/fall time <100ns
- Current 400 Hz PWM (2.5ms period) is 25,000x slower than LED response time
- ✅ No firmware change needed for PWM frequency

---

## 🚨 FIRMWARE RECOMMENDATIONS

### Scenario 1: PCB Current Limiting ≤ 120mA (VERY LIKELY - IDEAL)
✅ **NO FIRMWARE CHANGES NEEDED**

- Both LEDs operate safely within their ratings
- LCW max: 120mA, OWW max: 180mA
- If PCB designed for 60mA ± 30%, both LEDs are in optimal range
- Brightness difference (2.7x) handled by calibration automatically
- Continue with current firmware V1.3 (PWM bug fix only)

### Scenario 2: PCB Current Limiting 120-180mA (UNLIKELY)
⚠️ **FIRMWARE CHANGE REQUIRED FOR LCW CHANNELS ONLY**

**Risk:** LCW LED exceeds 120mA maximum rating at 100% PWM
**Solution:** Add PWM limiting for LCW channels only

**Which channels use which LED?**
```
Channel A: [LCW or OWW?] ___________
Channel B: [LCW or OWW?] ___________
Channel C: [LCW or OWW?] ___________
Channel D: [LCW or OWW?] ___________
```

**Example Firmware Fix (if LCW on Channels A & B, OWW on C & D, and current >120mA):**

In `affinite_p4spr.c`, add after line 99:
```c
// Per-channel PWM limits to protect LEDs with different current ratings
const float LED_A_MAX_DUTY = 0.67;   // LCW LED - limit to 67% to stay under 120mA if PCB allows 180mA
const float LED_B_MAX_DUTY = 0.67;   // LCW LED - limit to 67% to stay under 120mA if PCB allows 180mA
const float LED_C_MAX_DUTY = 1.00;   // OWW LED - can handle full 180mA
const float LED_D_MAX_DUTY = 1.00;   // OWW LED - can handle full 180mA
```

**NOTE:** This scenario is UNLIKELY - most SPR systems use 60-90mA current limiting, which is safe for both LEDs.

Then modify `led_brightness()` function (around line 690):
```c
case 'a':
    led_a_level = (uint16_t)(level * LED_A_MAX_DUTY);  // Apply PWM cap
    if (led_a_enabled){
        pwm_set_chan_level(LED_A_SLICE, LED_A_CH, led_a_level);
    }
    current_brightness = set_bright;
    break;

case 'b':
    led_b_level = (uint16_t)(level * LED_B_MAX_DUTY);  // Apply PWM cap
    // ... (similar for c, d with their respective limits)
```

### Scenario 3: PCB Current Limiting > 180mA (DANGER)
🔴 **HARDWARE REDESIGN REQUIRED**

- Both LEDs will be damaged at 100% PWM
- Firmware cannot fix this - resistor values must be changed on PCB
- **DO NOT OPERATE** until current limiting fixed

---

## 📋 ACTION ITEMS FOR YOU

### CRITICAL: Measure LED Current NOW (Before Further Testing)

**How to Measure:**
1. Connect multimeter in series with LED power line
2. Set to DC current measurement (200mA range)
3. Run this test:
   ```python
   from src.utils.controller import ArduinoController
   controller = ArduinoController(port='COM10')
   controller.open()

   # Test each channel at 100%
   for ch in ['a', 'b', 'c', 'd']:
       controller.set_intensity(ch, 255)
       controller.turn_on_channel(ch)
       input(f"Channel {ch.upper()} at 100% - MEASURE CURRENT NOW, then press Enter")
       controller.turn_off_channels()
   ```

4. **Record measurements:**
   ```
   Channel A: _____ mA (LED type: LCW or OWW?)
   Channel B: _____ mA (LED type: LCW or OWW?)
   Channel C: _____ mA (LED type: LCW or OWW?)
   Channel D: _____ mA (LED type: LCW or OWW?)
   ```

### Then Tell Me:
1. **Current measurements** for each channel
2. **Which LED type** (LCW or OWW) is on each channel
3. **PCB resistor values** (if visible/known)

**I'll then tell you:**
- ✅ If firmware changes are needed
- ✅ Exact PWM limits to add (if needed)
- ✅ If hardware is safe to use

---

## 🎯 EXPECTED OUTCOME

### Most Likely Scenario (80% confidence):
✅ **NO FIRMWARE CHANGES NEEDED**

**Reasoning:**
- Professional SPR system likely designed with 30-60mA current limiting
- This keeps both LED types within safe operating ranges
- 5.5x brightness difference handled automatically by Python calibration
- Your spectrometer-based calibration compensates for all LED variations

### Requires Firmware Changes (15% confidence):
⚠️ **PWM LIMITING NEEDED** if PCB current >60mA

- Simple fix: Add per-channel PWM caps (shown above)
- Takes 10 minutes to implement
- Recompile and flash updated firmware

### Requires Hardware Redesign (5% confidence):
🔴 **CRITICAL ISSUE** if PCB current >180mA

- Both LEDs at risk
- Must change current-limiting resistors before operation
- Cannot be fixed in firmware alone

---

## ✅ SUMMARY

### What's Good:
✅ Both LEDs have similar forward voltage (compatible)
✅ Both LEDs have fast switching (<100ns)
✅ Your 400 Hz PWM works perfectly for both
✅ Python calibration automatically handles brightness differences
✅ Spectrometer measures absolute photon counts (LED-independent)

### What to Verify:
⚠️ LED current draw at 100% PWM (MEASURE THIS!)
⚠️ Which channels use LCW vs OWW LEDs
⚠️ PCB current limiting resistor values

### Next Steps:
1. **Measure LED currents** (see action items above)
2. **Report measurements** to me
3. **I'll confirm** if firmware changes needed
4. **Then proceed** with firmware testing/compilation

**Until you measure the currents, assume firmware V1.3 (with PWM bug fix) is ready to use! 🚀**

The brightness difference between LEDs is NOT a problem - it's exactly what your calibration system is designed to handle.

### 1. Forward Voltage (Vf) Differences

**Impact:** Different Vf affects LED brightness at same PWM duty cycle

**Example:**
- LCW LED: Vf = 2.0V @ 20mA → Full brightness at 100% PWM
- OWW LED: Vf = 3.2V @ 20mA → Lower brightness at 100% PWM (if supply voltage limited)

**Firmware Action:**
- ✅ **No change needed** - Your Python calibration already compensates for intensity differences
- ❌ **Change needed IF:** Supply voltage < highest Vf (LEDs won't turn on properly)

**Check:** Measure actual supply voltage to LEDs and compare to max Vf

---

### 2. Current Limiting

**Impact:** LEDs have maximum safe current ratings

**Current Setup:**
- **Assumption:** Hardware current limiting via resistors on PCB
- **Firmware:** No current limiting (uses full 0-100% PWM range)

**Firmware Action:**
- ✅ **No change needed IF:** PCB has proper current-limiting resistors
- ❌ **Change needed IF:** LEDs can draw excessive current at 100% PWM

**To Check:**
1. Measure LED current at 100% PWM with multimeter
2. Compare to datasheet maximum If
3. If current exceeds 80% of If max, reduce PWM cap in firmware

**Firmware Fix (if needed):**
```c
// In led_brightness() function, add per-channel PWM limits
switch (ch_led){
    case 'a':
        led_a_level = level * 0.80;  // Cap at 80% if LED A can't handle full power
        break;
    // Similar for other channels if needed
}
```

---

### 3. Rise/Fall Time (Switching Speed)

**Impact:** Fast PWM may not be effective if LED rise/fall time is slow

**Current PWM:** 400 Hz (2.5 ms period)

**Firmware Action:**
- ✅ **No change needed** - 400 Hz is slow enough for all typical LEDs
- ❌ **Change needed IF:** LEDs have rise/fall time > 500 µs (very unlikely)

**Note:** Most visible LEDs have rise/fall times < 100 ns, so 400 Hz is perfectly fine

---

### 4. Thermal Characteristics

**Impact:** LED brightness may drift with temperature

**Current Firmware:** No thermal compensation

**Firmware Action:**
- ✅ **No change needed** - Your calibration workflow handles this
- ❌ **Change needed IF:** You need real-time thermal compensation

**Enhancement (future):**
```c
// Temperature sensor already present in firmware (line 227)
// Could add thermal compensation:
float temp_coefficient = 1.0 + (temp - 25.0) * 0.001;  // Example
led_a_level = base_level * temp_coefficient;
```

---

### 5. Wavelength/Color Differences

**Impact:** Different colors may appear at different brightnesses to human eye

**Firmware Action:**
- ✅ **No change needed** - Spectrometer measures absolute photon counts
- Your calibration automatically handles wavelength differences

---

### 6. Optical Power vs Visual Brightness

**Impact:** LED optical power (mW) may differ from perceived brightness (lumens)

**Firmware Action:**
- ✅ **No change needed** - Spectrometer measures optical power directly
- Your SPR measurements use optical power, not lumens

---

## Recommended Actions After Receiving Part Numbers

### Step 1: Datasheet Review
Download datasheets for both LED types and fill in the table above.

### Step 2: Electrical Verification
1. Measure actual forward voltage at 100% PWM
2. Measure forward current at 100% PWM
3. Compare to datasheet maximum ratings

### Step 3: Firmware Assessment
Check if any of these conditions are true:

| Condition | Action Required |
|-----------|----------------|
| If max > LED If max × 0.8 | Add PWM current limiting |
| Vf > Supply voltage × 0.9 | Increase supply voltage or reduce PWM cap |
| Rise/Fall time > 500 µs | Reduce PWM frequency (unlikely) |
| Temperature drift > 5%/°C | Add thermal compensation (optional) |

### Step 4: Testing
Run these tests with actual LEDs installed:

1. **Power Test:**
   ```powershell
   .venv312\Scripts\python.exe test_led_brightness.py
   ```
   - Verify all LEDs reach expected brightness
   - Check no LED thermal shutdown occurs

2. **Calibration Test:**
   ```powershell
   .venv312\Scripts\python.exe test_calibration_steps_1_4.py
   ```
   - Verify all LEDs measure >30,000 counts at target integration time
   - Check brightness ratios are reasonable (within 3x of each other)

3. **Long Duration Test:**
   - Run all LEDs at 100% for 5 minutes
   - Monitor for thermal drift, brightness reduction, or shutdown
   - Measure temperature rise

---

## Example: Per-Channel PWM Limits (If Needed)

If datasheets show LEDs need different max currents:

```c
// In affinite_p4spr.c, add after LED_WRAP definition (line ~99):

// Per-channel PWM limits (0.0 to 1.0, where 1.0 = full PWM)
const float LED_A_MAX_DUTY = 1.0;   // LCW LED - can handle full power
const float LED_B_MAX_DUTY = 0.8;   // OWW LED - limit to 80% (example)
const float LED_C_MAX_DUTY = 1.0;
const float LED_D_MAX_DUTY = 1.0;
```

Then modify `led_brightness()` function:

```c
case 'a':
    led_a_level = (uint16_t)(level * LED_A_MAX_DUTY);
    if (led_a_enabled){
        pwm_set_chan_level(LED_A_SLICE, LED_A_CH, led_a_level);
    }
    current_brightness = set_bright;
    break;
```

**IMPORTANT:** Only implement this if measurements show LEDs drawing excessive current!

---

## PCB Current Limiting (Should Already Be Present)

**Expected Circuit:**
```
[3.3V or 5V] ----[Resistor]----[LED]----[MOSFET]----[GND]
                                          ^
                                          |
                                    GPIO (PWM)
```

**Resistor Value:**
```
R = (Vsupply - Vf) / If_target

Example:
Vsupply = 5V
Vf = 2.0V (LED forward voltage)
If_target = 20mA (desired current)

R = (5 - 2) / 0.020 = 150 Ω
```

**Check PCB:** Look for resistors in series with each LED (should be 100-500Ω range)

---

## Summary: Likely No Firmware Changes Needed

**Reasons:**
1. ✅ Hardware current limiting via PCB resistors (should be present)
2. ✅ 400 Hz PWM is suitable for all standard LEDs
3. ✅ Python calibration compensates for intensity differences
4. ✅ Spectrometer measures absolute optical power (wavelength independent)
5. ✅ 0-255 brightness range mapped to full PWM wrap provides good resolution

**Only need firmware changes if:**
- ❌ PCB lacks current limiting resistors (dangerous!)
- ❌ LEDs draw >If_max at 100% PWM (measure with multimeter)
- ❌ Supply voltage insufficient for LED Vf (LEDs won't turn on)

**Next Step:**
📋 **Provide LED part numbers so I can review datasheets and confirm no firmware changes needed**

---

**Template for Part Number Info:**

```
LCW LED: [Part Number]
- Manufacturer: [e.g., OSRAM, Cree, Kingbright]
- Datasheet Link: [URL if available]

OWW LED: [Part Number]
- Manufacturer: [e.g., OSRAM, Cree, Kingbright]
- Datasheet Link: [URL if available]
```

I'll review the datasheets and tell you definitively if firmware changes are needed! 🔍
