# LED CALIBRATION LOGIC - LOCKED SPECIFICATION

**Last Updated**: November 24, 2025
**Status**: LOCKED - Do not modify without review

---

## SINGLE SOURCE OF TRUTH: device_config.json

**ALL calibration decisions are based EXCLUSIVELY on device_config.json**

❌ **NOT USED**: Optical calibration files, cached values, hardcoded defaults
✅ **ONLY USED**: `device_config.json` via `DeviceConfiguration.load_led_calibration()`

---

## OPTICAL SYSTEM MODES (How Data is Recorded)

**CRITICAL**: The optical system mode determines HOW LED intensity and integration time are recorded in device_config.json. **This is THE MAIN PLACE impacted by the mode choice.**

### Mode 1: STANDARD (Global Integration Time) - DEFAULT
**Philosophy**: ONE integration time, VARIABLE LED intensities per channel
**Config**: `settings.USE_ALTERNATIVE_CALIBRATION = False`

**Calibration Process**:
- Step 1: Find single optimal integration time (works for all channels)
- Step 2: Optimize LED intensity PER CHANNEL to reach target signal
- Result: All channels use SAME integration time, but DIFFERENT LED intensities

**Recorded in device_config.json**:
```json
{
  "led_calibration": {
    "integration_time_ms": 93,                           // SAME for all channels
    "s_mode_intensities": {"a": 187, "b": 203, "c": 195, "d": 178},  // VARIABLE
    "p_mode_intensities": {"a": 238, "b": 255, "c": 245, "d": 229}   // VARIABLE
  }
}
```

**Best for**: Circular polarizers where LED intensity affects polarization coupling
**Timing**: ~200ms/channel ≈ 1Hz per channel

### Mode 2: ALTERNATIVE (Global LED Intensity) - EXPERIMENTAL
**Philosophy**: FIXED LED intensity (255), VARIABLE integration time per channel
**Config**: `settings.USE_ALTERNATIVE_CALIBRATION = True`

**Calibration Process**:
- Step 1: Set ALL LEDs to maximum (255) for consistency and max SNR
- Step 2: Optimize integration time PER CHANNEL to reach target signal
- Result: All channels use SAME LED intensity (255), but DIFFERENT integration times

**Recorded in device_config.json**:
```json
{
  "led_calibration": {
    "calibration_method": "alternative",
    "integration_time_ms": 120,                     // MAX integration across channels
    "per_channel_integration_times": {              // VARIABLE per channel
      "a": 85,
      "b": 95,
      "c": 120,
      "d": 110
    },
    "s_mode_intensities": {"a": 255, "b": 255, "c": 255, "d": 255},  // FIXED
    "p_mode_intensities": {"a": 255, "b": 255, "c": 255, "d": 255}   // FIXED
  }
}
```

**Benefits**: Better frequency, excellent SNR, LED consistency at max current
**Trade-offs**: Variable integration per channel, requires per-channel timing during acquisition

### Downstream Effects of Mode Choice:
1. **device_config.json structure** (MAIN IMPACT - how data is saved/loaded)
2. **Fast-track validation** (standard validates LED values, alternative validates integration times)
3. **Live acquisition** (standard uses global integration, alternative uses per-channel)
4. **QC validation** (standard compares LED intensities, alternative compares integration times)

---

## CALIBRATION MODE DECISION (Within Each Optical System Mode)

### Fast-Track Mode
**Trigger**: `device_config.json` contains valid LED calibration data
**Process**:
1. Load saved LED intensities from device config
2. Validate each LED value (1-255 range, not None)
3. Test EACH saved value on real hardware
4. Measure actual signal and verify in acceptable range (30-80% of detector max)
5. If validation passes → Use saved value (fast!)
6. If validation fails → Re-calibrate that channel from scratch
7. Integration time is ALWAYS calibrated (never cached - hardware dependent)

**Time Savings**: ~80% faster if values still valid

### Full Calibration Mode
**Trigger**: `device_config.json` missing LED calibration data OR data invalid
**Process**:
1. Calibrate integration time from scratch (binary search)
2. Calibrate LED intensities from scratch (binary search per channel)
3. All measurements done on real hardware
4. No cached or default values used

---

## HARDWARE VALIDATION (BOTH MODES, BOTH OPTICAL SYSTEMS)

**Every calibration includes these safety checks**:

1. **Pre-flight check**: Test hardware responds before starting
2. **Initial signal check**: LED at max must produce >1000 counts
3. **Response validation**: Signal must change when LED intensity changes
4. **Final accuracy check**: Calibration must achieve target within 10% error
5. **Post-calibration verification**: All channels tested to produce expected signal

**Any hardware validation failure → Calibration aborts with clear error**

---

## CALIBRATION SAVE (CRITICAL)

**After successful calibration, ALL results saved to device_config.json**:

**STANDARD Mode**:
```python
device_config.save_led_calibration(
    integration_time_ms=93,                           # Global integration time
    s_mode_intensities={'a': 187, 'b': 203, ...},     # Variable per channel
    p_mode_intensities={'a': 238, 'b': 255, ...},     # Variable per channel
    s_ref_spectra=result.ref_sig,
    s_ref_wavelengths=result.wave_data
)
```

**ALTERNATIVE Mode**:
```python
device_config.save_led_calibration(
    integration_time_ms=120,                          # MAX integration time
    s_mode_intensities={'a': 255, 'b': 255, ...},     # Fixed at 255
    p_mode_intensities={'a': 255, 'b': 255, ...},     # Fixed at 255
    s_ref_spectra=result.ref_sig,
    s_ref_wavelengths=result.wave_data,
    calibration_method='alternative',
    per_channel_integration_times={'a': 85, 'b': 95, 'c': 120, 'd': 110}
)
```

**Location**: `calibration_coordinator.py::_save_calibration_to_device_config()`

**This save is REQUIRED** - without it, next calibration will be full (not fast-track)

---

## DATA FLOW

```
┌─────────────────────────────────────────────────────────────┐
│  START CALIBRATION                                          │
│  Check settings.USE_ALTERNATIVE_CALIBRATION                 │
└─────────────────────────────────────────────────────────────┘
                           ↓
              ┌────────────┴────────────┐
              │                         │
        FALSE │                         │  TRUE
              ↓                         ↓
   ┌──────────────────────┐  ┌──────────────────────┐
   │  STANDARD MODE       │  │  ALTERNATIVE MODE    │
   │  (Global Int Time)   │  │  (Global LED 255)    │
   └──────────────────────┘  └──────────────────────┘
              │                         │
              └────────────┬────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  Check device_config.json for saved LED calibration         │
│  Method: device_config.load_led_calibration()               │
└─────────────────────────────────────────────────────────────┘
                           ↓
              ┌────────────┴────────────┐
              │                         │
         YES  │                         │  NO
              ↓                         ↓
   ┌──────────────────────┐  ┌──────────────────────┐
   │  FAST-TRACK MODE     │  │  FULL CALIBRATION    │
   │                      │  │                      │
   │  1. Load saved LEDs  │  │  1. Calibrate int    │
   │  2. Calibrate int    │  │  2. Find LEDs from   │
   │  3. Test each LED    │  │     scratch          │
   │     on hardware      │  │  3. Measure refs     │
   │  4. Re-cal if fail   │  │                      │
   │  5. Measure refs     │  │                      │
   └──────────────────────┘  └──────────────────────┘
              │                         │
              └────────────┬────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  SAVE RESULTS TO device_config.json                         │
│  Method: device_config.save_led_calibration(...)            │
│                                                              │
│  Saved data:                                                │
│  - integration_time_ms                                      │
│  - s_mode_intensities {'a': 198, 'b': 203, ...}           │
│  - p_mode_intensities {'a': 215, 'b': 220, ...}           │
│  - s_ref_spectra (numpy arrays per channel)                │
│  - s_ref_wavelengths (wavelength array)                    │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  NEXT CALIBRATION → Fast-track mode (uses saved values)     │
└─────────────────────────────────────────────────────────────┘
```

---

## KEY FILES

### 1. LED Calibration Logic
**File**: `utils/led_calibration.py::perform_full_led_calibration()`
**Lines**: ~1900-2000 (LED decision logic)

**Key Code**:
```python
# Load from device config ONLY
saved_led_intensities = None
if device_config is not None:
    cal_data = device_config.load_led_calibration()
    if cal_data and 's_mode_intensities' in cal_data:
        saved_led_intensities = cal_data['s_mode_intensities']

# Decision: Fast-track or Full
use_fast_track = (saved_led_intensities is not None
                  and all_channels_have_valid_values)
```

### 2. Save Calibration Results
**File**: `core/calibration_coordinator.py::_save_calibration_to_device_config()`
**Lines**: ~563-630

**Key Code**:
```python
device_config.save_led_calibration(
    integration_time_ms=integration_time,
    s_mode_intensities=s_mode_intensities,
    p_mode_intensities=p_mode_intensities,
    s_ref_spectra=s_ref_spectra,
    s_ref_wavelengths=s_ref_wavelengths
)
```

### 3. Device Config API
**File**: `utils/device_configuration.py`
**Methods**:
- `load_led_calibration()` - Load saved calibration (line ~1118)
- `save_led_calibration()` - Save new calibration (line ~602)

---

## VALIDATION RULES

### Fast-Track LED Validation
Each saved LED value must pass:
1. **Range check**: 1 ≤ LED ≤ 255
2. **Hardware test**: Set LED, measure signal
3. **Signal check**: Signal > 500 counts (not noise)
4. **Range check**: 30% ≤ signal ≤ 80% of detector max

**If any check fails → Re-calibrate that channel**

### Integration Time
**NEVER cached or fast-tracked** - always calibrated because:
- Depends on current temperature
- Depends on optical coupling quality
- Depends on prism/water contact
- Hardware state can change between calibrations

---

## LOGGING EXPECTATIONS

### Fast-Track Mode
```
📋 Found saved LED calibration in device_config.json (from 2025-11-24T16:30:15)
   Ch A: LED = 198/255
   Ch B: LED = 203/255
🚀 FAST-TRACK MODE: All 4 channels have valid LED values in device config
   Testing Ch A: Using saved LED=198 from device config
   ✅ Ch A: LED 198 validated (signal: 19234 counts, range: 9830-26213)
✅ Fast-track validation passed for: A, B, C, D
```

### Full Calibration Mode
```
ℹ️ No saved LED calibration in device config - running FULL CALIBRATION
📊 FULL CALIBRATION MODE: Finding optimal LED intensities from hardware measurements
   Calibrating Ch A (using real hardware measurements)...
   ✅ Ch A: Calibrated to 19661 counts at LED=198
```

### Save Confirmation
```
💾 LED calibration saved to device_config.json (single source of truth)
   Integration: 42ms, S-mode LEDs: {'a': 198, 'b': 203, 'c': 195, 'd': 201}
```

---

## ERROR SCENARIOS

### Hardware Not Responding
```
❌ PRE-FLIGHT CHECK FAILED: No signal detected from hardware
   LED A set to 200 but signal is only 45 counts
   Possible causes:
   - Hardware disconnected
   - LEDs not working
   - No water/prism on sensor
```

### Fast-Track Validation Failed
```
⚠️ Ch A: Signal too weak (5234 < 9830), recalibrating...
⚠️ Fast-track validation failed for: A, C - recalibrated from scratch
```

### Missing Device Config Data
```
ℹ️ No saved LED calibration in device config - running FULL CALIBRATION
```

---

## MODIFICATION RULES

**DO NOT MODIFY** without understanding full impact:

1. ❌ **Do not add** alternative sources for LED values (optical cal files, hardcoded defaults, etc.)
2. ❌ **Do not cache** integration time - it must always be calibrated
3. ❌ **Do not skip** hardware validation checks
4. ❌ **Do not change** fast-track decision logic without updating this doc
5. ✅ **Always save** calibration results to device_config.json after success
6. ✅ **Always use** `device_config.load_led_calibration()` for fast-track decision
7. ✅ **Always validate** saved values on real hardware before using them

---

## TESTING CHECKLIST

To verify calibration logic is working:

- [ ] Delete device_config.json → Should run FULL calibration
- [ ] After calibration → Check device_config.json has `led_calibration` section
- [ ] Run calibration again → Should run FAST-TRACK mode
- [ ] Modify saved LED value to invalid (e.g., 0) → Should run FULL calibration
- [ ] Check logs show correct mode (fast-track vs full)
- [ ] Verify hardware validation runs (pre-flight, post-calibration checks)
- [ ] Confirm integration time is calibrated in both modes

---

**END OF SPECIFICATION**
