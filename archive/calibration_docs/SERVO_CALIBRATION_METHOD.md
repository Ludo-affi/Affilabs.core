# 🔧 SERVO CALIBRATION METHOD - REFERENCE DOCUMENT

**Status**: ✅ **PRODUCTION REFERENCE** - This is the authoritative calibration method
**Version**: V1.9
**Date**: December 5, 2025
**Firmware**: V1.9 with multi-LED support
**Hardware**: P4SPR with USB4000/Flame-T detector

---

## 📋 OVERVIEW

This document defines the **standard method** for automatic polarizer servo calibration. This is the **reference implementation** used across all P4SPR systems.

### Key Features
- ✅ **Batch spectrum acquisition** - 400 spectra in single 4-second sweep
- ✅ **Timestamp correlation** - Links spectra to servo positions post-acquisition
- ✅ **Adaptive P-finding** - Different strategies for circular vs barrel polarizers
- ✅ **EEPROM persistence** - Saves S/P positions to device memory
- ✅ **<8 second calibration** - Fast, automated, reliable

---

## 🎯 CALIBRATION WORKFLOW

### **Phase 1: Coarse Sweep (S-Position Finding)**
**Duration**: 4 seconds
**Objective**: Find maximum intensity position (S-position - parallel polarization)

#### Sweep Parameters (COARSE)
```python
Range:               0-240° (extended to ensure full rotation coverage)
Step size:           12° (240°/20 = 20 positions)
Servo settling:      100ms per position
Acquisition period:  100ms per position
Total per position:  200ms
Total sweep time:    20 × 0.2s = 4 seconds
```

#### Spectrum Acquisition Strategy
```python
Integration time:    10ms
Expected spectra:    ~400 total (20 per position)
Sampling strategy:   Continuous acquisition with timestamp correlation
```

**Method**:
1. Start servo sweep at t=0 from 0°
2. Move servo to each position (12° steps)
3. Wait 100ms for servo to settle
4. Acquire spectra continuously for 100ms (~10 spectra)
5. Record timestamp for each spectrum
6. After sweep completes, correlate spectra to positions by timestamp
7. Average ~10 spectra per position to reduce noise
8. Build intensity map: {position: averaged_intensity}
9. Find S-position as maximum intensity in map

**Why Batch Acquisition?**
- ✅ No delays between spectra - continuous high-speed acquisition
- ✅ ~10 spectra averaged per position improves SNR by √10 (~3.2x)
- ✅ Timestamps allow post-processing correlation
- ✅ Captures full polarization curve with high resolution
- ✅ Single sweep is faster and more consistent than dual-sweep averaging

---

### **Phase 2: Polarizer Classification**
**Duration**: <100ms (analysis only)
**Objective**: Determine polarizer type (circular vs barrel)

#### Classification Logic
```python
Dark count threshold:     4000 counts (Ocean Optics detector)
Dark position threshold:  10 positions

IF dark_positions < 10:
    polarizer_type = "CIRCULAR"
    P_strategy = "find minimum intensity ±5° from S+90°"
ELSE:
    polarizer_type = "BARREL"
    P_strategy = "find maximum intensity ±15° from S+90°"
```

**Circular Polarizers**:
- Show ~dark counts for < 10 positions (narrow extinction region)
- P-position is 90° from S at **minimum intensity**
- Scan ±5° around expected P with FINE steps (3°)

**Barrel Polarizers**:
- Show dark counts for ≥ 10 positions (broad extinction region)
- P-position is 90° from S at **maximum intensity** in dark region
- Two-phase refinement: MEDIUM (±15°) then FINE (±6°)

---

### **Phase 3: P-Position Refinement**
**Duration**: 1-3 seconds (depends on polarizer type)
**Objective**: Find precise P-position (perpendicular polarization)

#### For Circular Polarizers
```python
Expected P:       (S + 90°) mod 360°
Scan range:       ±5° around expected P
Step size:        3° (FINE)
Delay per step:   150ms
Positions:        ~4 positions
Duration:         ~0.6 seconds
Strategy:         Find MINIMUM intensity
```

#### For Barrel Polarizers
```python
# Phase 1: Medium sweep
Expected P:       (S + 90°) mod 360°
Scan range:       ±15° around expected P
Step size:        6° (MEDIUM)
Delay per step:   150ms
Positions:        ~5 positions
Duration:         ~0.75 seconds
Strategy:         Find rough MAXIMUM in dark region

# Phase 2: Fine sweep
Scan range:       ±6° around rough maximum
Step size:        3° (FINE)
Delay per step:   150ms
Positions:        ~4 positions
Duration:         ~0.6 seconds
Strategy:         Find precise MAXIMUM
```

---

## ⚙️ SERVO SPEED PRESETS

### Reference Configuration (servo_speed_presets.py)

```python
SPEED_PRESETS = {
    'coarse': {
        'step_size': 12,        # degrees
        'step_delay': 0.1,      # 100ms acquisition period
        'settling_time': 0.1,   # 100ms servo settling
        'total_time': 0.2,      # 200ms per position
        'positions': 20,
        'sweep_time': 4.0       # seconds
    },
    'medium': {
        'step_size': 6,         # degrees
        'step_delay': 0.15,     # 150ms per position
        'positions': 30,        # for full 180° sweep
        'use_case': 'P-position refinement (barrel)'
    },
    'fine': {
        'step_size': 3,         # degrees
        'step_delay': 0.15,     # 150ms per position
        'positions': 60,        # for full 180° sweep
        'use_case': 'Precise P-position detection'
    }
}
```

### Timing Breakdown
```
Coarse sweep:   200ms × 20 positions = 4.0s
Medium sweep:   150ms × 5 positions  = 0.75s (typical for barrel)
Fine sweep:     150ms × 4 positions  = 0.6s  (typical for both types)

Total calibration: ~6-7 seconds + LED setup + EEPROM save = <8 seconds
```

---

## 🔬 DETECTOR INTEGRATION

### USB4000/Flame-T Configuration
```python
Integration time:     10ms (optimized for LED intensity)
Max counts:           65535
Pixels:               3840
Backend:              pyseabreeze (pure Python, WinUSB compatible)
```

### Intensity Calculation
```python
def calculate_intensity_metric(spectrum):
    """
    Use top 50 pixels averaged to get peak intensity.
    More robust than max() for noisy data.
    """
    top_pixels = np.partition(spectrum, -50)[-50:]
    return np.mean(top_pixels)
```

---

## 💾 EEPROM PERSISTENCE

### Save Sequence
```python
# 1. Set S and P positions in firmware RAM
cmd = f'sv{s_deg:03d}{p_deg:03d}\n'  # Format: sv093000 (S=93°, P=0°)
send_command(cmd)

# 2. Save to EEPROM
send_command('sf\n')  # Flash save
time.sleep(0.5)       # Wait for EEPROM write

# 3. Verify saved positions
send_command('sr\n')  # Servo read
response = read_response()

# 4. Move to S position to confirm
send_command('ss\n')  # Move to saved S position
```

### Firmware Commands (V1.9)
```
ss  - Move servo to saved S position
sp  - Move servo to saved P position
sv{S:03d}{P:03d} - Set S and P positions (000-180°)
sf  - Save current positions to EEPROM
sr  - Read positions from EEPROM
se  - Enable servo
```

---

## 📊 EXAMPLE CALIBRATION OUTPUT

```
======================================================================
AUTOMATIC POLARIZER CALIBRATION - V1.9
======================================================================

[1/7] Enabling servo...
   ✅ Servo enabled

[2/7] Setting up illumination...
   Setting all LEDs to 5% intensity (12/255)...
   ✅ LEDs ON

[3/7] Configuring servo for coarse sweep...
   Servo speed: 12° steps, 100ms delay

[4/7] Performing batch coarse sweep (0-240°)...
   Strategy: Collect ~400 spectra (20 per position) with proper servo settling
   Sweep duration: 4.0s
   Expected spectra: ~400 (20 per position)

   Starting servo sweep and spectrum acquisition...
   ✅ Batch acquisition complete: 387 spectra collected

   Analyzing batch data...
   Position 0°: 18 spectra averaged, intensity=5823.2
   Position 60°: 19 spectra averaged, intensity=7234.1
   Position 120°: 20 spectra averaged, intensity=6891.4
   ✅ Batch analysis complete: 20 positions mapped

[5/7] Batch sweep complete...
   ✅ Total positions mapped: 20

[6/7] Analyzing intensity map...
   ✅ S position found: 93° (intensity: 7826.3)

[7/7] Finding P position...
   Analyzing polarizer type...
   Dark positions found: 0
   ✅ Polarizer type: CIRCULAR

   Finding P position for circular polarizer...
   Expected P near: 3°
   Scanning 0° to 8° (±5°) for minimum...
   ✅ P position found: 0° (intensity: 5750.5)

Finalizing calibration...
   S = 93°, P = 0°
   ✅ Calibration saved to device config and EEPROM

======================================================================
✅ CALIBRATION COMPLETE!
======================================================================

Results:
   Polarizer Type: CIRCULAR
   S Position: 93°
   P Position: 0°
   Batch sweep: ~400 spectra over 20 positions = 4s
   P refinement: ~1-2s (depending on polarizer type)
   Total time: <8 seconds

   ✅ Calibration saved to device config and EEPROM
   ✅ Use OEM commands 'ss' and 'sp' to move to saved positions
======================================================================
```

---

## 🚀 PERFORMANCE CHARACTERISTICS

### Speed
- **Coarse sweep**: 4 seconds (20 positions with batch acquisition)
- **P refinement**: 1-3 seconds (depending on polarizer type)
- **Total time**: <8 seconds (including LED setup and EEPROM save)

### Accuracy
- **Position resolution**: 3° (fine sweep step size)
- **Measurement SNR**: ~3.2x improvement from averaging 10 spectra
- **Repeatability**: ±3° (limited by step size and servo mechanics)

### Robustness
- ✅ **Servo settling time**: 100ms ensures stable positioning
- ✅ **Batch correlation**: Timestamps compensate for timing jitter
- ✅ **Adaptive strategy**: Different logic for circular vs barrel polarizers
- ✅ **Extended range**: 0-240° sweep catches edge cases near 180°

---

## 🔧 TROUBLESHOOTING

### Issue: Servo doesn't move
**Causes**:
- Servo not enabled (`se` command)
- Wrong command format (use `sv{S:03d}{P:03d}` then `ss` or `sp`)
- Servo power disconnected

**Fix**:
```python
ser.write(b'se\n')  # Enable servo first
time.sleep(0.5)
ser.write(b'sv093000\n')  # Set positions
ser.write(b'ss\n')  # Move to S position
```

### Issue: Not enough spectra collected
**Causes**:
- Integration time too long (>10ms)
- Detector connection issues
- Insufficient acquisition period

**Fix**:
```python
detector.set_integration(10)  # Set to 10ms
# Verify: 100ms period / 10ms integration = ~10 spectra per position
```

### Issue: S and P positions incorrect
**Causes**:
- LED intensity too low (< 5%)
- Dark counts dominating signal
- Polarizer classification wrong

**Fix**:
```python
# Increase LED intensity
set_led_intensity(10)  # Try 10% instead of 5%

# Check detector response
spectrum = detector.read_intensity()
print(f"Signal range: {spectrum.min():.0f} - {spectrum.max():.0f}")
# Should be > 4000 counts for good signal
```

---

## 📁 FILES

### Core Implementation
- **`auto_polarizer_calibration_v1.9.py`** - Main calibration script
- **`src/utils/servo_speed_presets.py`** - Speed preset definitions
- **`src/utils/usb4000_wrapper.py`** - Detector driver

### Firmware
- **`PicoP4SPR_Firmware/affinite_p4spr.c`** - V1.9 firmware source
- **`PicoP4SPR_Firmware/build/affinite_p4spr_v1.9.uf2`** - Compiled firmware

### Documentation
- **`SERVO_CALIBRATION_METHOD.md`** - **THIS DOCUMENT** (Reference)
- **`SERVO_ROTATION_FIX.md`** - Historical: Why 3-step command sequence needed
- **`BASELINE_RECORDING_AND_PEAK_TRACKING.md`** - Integration with main app

---

## ⚠️ IMPORTANT NOTES

1. **This is the reference calibration method** - Do not modify without testing
2. **Batch acquisition is critical** - Single sweep with timestamp correlation
3. **Servo settling time is mandatory** - 100ms minimum before acquisition
4. **Polarizer classification drives P-finding** - Different strategies for types
5. **EEPROM save preserves calibration** - Survives power cycles
6. **Integration time = 10ms** - Optimized for 5% LED intensity

---

## 🔄 VERSION HISTORY

**V1.9** (December 5, 2025):
- Added batch spectrum acquisition
- Timestamp-based position correlation
- Extended range to 0-240°
- Optimized timing: 100ms settling + 100ms acquisition
- Adaptive P-finding for circular vs barrel polarizers
- Total calibration time reduced to <8 seconds

**V1.8** (Previous):
- Dual-sweep averaging (6 seconds)
- Sequential acquisition (1 spectrum per position)
- 0-180° range only
- Fixed P-finding strategy

---

## 📞 CONTACT

For questions or issues with this calibration method:
- Check troubleshooting section first
- Review example output for expected behavior
- Verify firmware version (must be V1.9)
- Ensure USB4000 detector connected and working

---

**END OF REFERENCE DOCUMENT**
