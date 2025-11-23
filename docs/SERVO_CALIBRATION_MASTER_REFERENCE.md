# Servo Calibration System Master Reference

**AUTHORITATIVE DOCUMENTATION - Last Updated: November 23, 2025**

This document describes the complete servo/polarizer calibration system for finding optimal S and P positions.

---

## 📂 File Locations

### ✅ ACTIVE Implementation (Use These)

**Primary Calibration Module**:
- `Affilabs.core beta/utils/servo_calibration.py` ← **MASTER IMPLEMENTATION**

**Integration Point**:
- `utils/spr_calibrator.py::auto_polarize()` - Calls servo_calibration module

### 📚 Reference Only (Do Not Modify)

**Old Software**:
- `Old software/utils/servo_calibration.py` - Original implementation (reference only)
- `Old software/test_servo_calibration.py` - Test script (not actively used)

---

## 🎯 Entry Point Function

```python
from utils.servo_calibration import auto_calibrate_polarizer

result = auto_calibrate_polarizer(
    usb=usb,
    ctrl=ctrl,
    require_water=True,  # For circular polarizers
    polarizer_type="circular"  # or "barrel"
)

if result and result['success']:
    print(f"S position: {result['s_pos']}°")
    print(f"P position: {result['p_pos']}°")
    print(f"S/P ratio: {result['sp_ratio']:.2f}×")
    print(f"Dip depth: {result['dip_depth_percent']:.1f}%")
```

**Returns**: Dict with validation results OR None if failed

**Does NOT automatically save** - caller must handle user confirmation and save to device_config.

---

## 🔄 Calibration Methods

### Method 1: Circular Polarizer (Standard)

**Function**: `perform_quadrant_search(usb, ctrl)`

**Algorithm**:
```
Phase 1: Coarse Search (5 positions)
  ├─ Measure: 10°, 50°, 90°, 130°, 170°
  ├─ ROI: 600-750nm (SPR region)
  └─ Find: Approximate P position (minimum intensity)

Phase 2: Refinement (±20° around P)
  ├─ Measure: P-20°, P-10°, P, P+10°, P+20°
  └─ Find: Exact P position (strongest SPR absorption)

Phase 3: Calculate S (90° offset)
  ├─ S = P ± 90° (within 10-170° range)
  └─ Measure: Verify S intensity

Phase 4: Validation (transmission-based)
  ├─ Calculate: Transmission = P / S × 100%
  ├─ Check: Dip depth >10%, wavelength 590-670nm
  ├─ Check: S > P, S/P ratio >1.3×, no saturation
  └─ Return: Validated positions OR None
```

**Total Measurements**: ~13 (vs 33+ for full sweep)

**Requirements**:
- Water on sensor (for SPR detection)
- Servo range: 10-170°
- ROI: 600-750nm

**Validation**:
- Transmission dip depth ≥10%
- Resonance wavelength: 590-670nm
- S > P (no inversion)
- S/P ratio ≥1.3×
- No saturation (<95% of max counts)

### Method 2: Barrel Polarizer (Discrete Windows)

**Function**: `perform_barrel_window_search(usb, ctrl)`

**Algorithm**:
```
Phase 1: Full Sweep (find all windows)
  ├─ Measure: Every 5° from 10-170°
  ├─ Detect: Positions above threshold (intensity peaks)
  └─ Result: List of high-transmission positions

Phase 2: Cluster Detection (group into 2 windows)
  ├─ Gap detection: Separate by >15° gaps
  ├─ Keep: 2 largest clusters
  └─ Result: Window 1 positions, Window 2 positions

Phase 3: Find Window Centers
  ├─ For each window: Find position with max intensity
  └─ Result: 2 peak positions

Phase 4: Identify S vs P (SPR signature)
  ├─ Measure: Both windows in S-mode and P-mode
  ├─ Calculate: Transmission spectrum for each
  ├─ Analyze: Which shows stronger SPR dip
  ├─ Decision: Stronger dip → P window
  └─ Result: S position, P position

Phase 5: Validation
  ├─ Check: Separation >70°
  ├─ Check: S/P ratio >1.3×
  └─ Return: Validated positions OR None
```

**Total Measurements**: ~35 (full sweep required)

**Key Differences from Circular**:
- Does NOT require water (can find windows by intensity alone)
- Windows NOT exactly 90° apart (physical constraint)
- Must identify which is S vs P (not predetermined)
- Windows span multiple positions (clusters)

**Validation**:
- Window separation ≥70°
- S/P ratio ≥1.3×
- P window shows SPR dip when water present

---

## 📊 Helper Functions

### `check_water_presence(usb, ctrl, s_pos, p_pos)`

Checks for water on sensor by analyzing transmission spectrum.

**Method**:
1. Measure S-pol and P-pol at given positions
2. Calculate transmission = P / S × 100%
3. Analyze SPR ROI (600-750nm) for dip
4. Check dip depth ≥10% and transmission <100%

**Returns**: `(has_water, transmission_min, dip_depth_percent)`

### `validate_positions_with_transmission(usb, ctrl, s_pos, p_pos)`

Validates S/P positions using comprehensive transmission analysis.

**Checks**:
1. ✅ No saturation (S and P <95% max counts)
2. ✅ S > P (no inversion at ROI level)
3. ✅ S/P ratio ≥1.3×
4. ✅ Transmission dip depth ≥10%
5. ✅ Transmission <100% (no inversion)
6. ✅ Resonance wavelength 590-670nm (warning if out of range)

**Returns**: `(is_valid, validation_results_dict)`

### `get_roi_intensity(spectrum, wavelengths)`

Extracts maximum intensity from SPR ROI (600-750nm).

**Purpose**: Focus measurements on SPR-relevant wavelength region.

---

## 🔧 Configuration Constants

```python
# Servo range
MIN_ANGLE = 10          # Start of servo range (degrees)
MAX_ANGLE = 170         # End of servo range (degrees)

# ROI for SPR measurements
ROI_MIN_WL = 600        # Minimum wavelength (nm)
ROI_MAX_WL = 750        # Maximum wavelength (nm)

# Resonance validation
MIN_RESONANCE_WL = 590  # Minimum valid resonance (nm)
MAX_RESONANCE_WL = 670  # Maximum valid resonance (nm)

# Timing
SETTLING_TIME = 0.2     # Servo settling time (seconds)
MODE_SWITCH_TIME = 0.1  # S/P mode switch time (seconds)

# Validation thresholds
MIN_SEPARATION = 80                # Minimum S-P separation (degrees)
MAX_SEPARATION = 100               # Maximum S-P separation (degrees)
MIN_SP_RATIO = 1.3                 # Minimum S/P intensity ratio
IDEAL_SP_RATIO = 1.5               # Ideal S/P intensity ratio
MIN_DIP_DEPTH_PERCENT = 10.0       # Minimum transmission dip (%)
MAX_DETECTOR_COUNTS = 62000        # Flame-T maximum counts
SATURATION_THRESHOLD = 0.95        # Saturation warning (95%)
```

---

## 💾 Save Flow

**Correct Implementation** (as designed):

```python
# 1. Run calibration
result = auto_calibrate_polarizer(usb, ctrl, polarizer_type="circular")

if result and result['success']:
    # 2. Show confirmation dialog to user
    show_confirmation_dialog(result)

    # 3. If user accepts:
    if user_accepted:
        # Save to device_config.json
        save_to_device_config(result['s_pos'], result['p_pos'])

        # Apply to hardware
        ctrl.servo_set(s=result['s_pos'], p=result['p_pos'])

        # 4. Later: User clicks "Push to EEPROM"
        # This syncs entire device_config → EEPROM
```

**Key Points**:
- ❌ Never auto-save to EEPROM
- ✅ Always require user confirmation
- ✅ Save to device_config first
- ✅ EEPROM is separate manual backup

---

## 🧪 Testing Functions

### `perform_full_sweep_fallback(usb, ctrl)`

Legacy full-sweep method using scipy peak detection.

**Status**: Fallback only (not primary method)
**Use**: If quadrant search fails on circular polarizers
**Measurements**: 33+ positions
**Method**: scipy.signal.find_peaks()

---

## 📖 Related Documentation

**Core References**:
- `docs/S_POL_P_POL_SPR_MASTER_REFERENCE.md` - S-pol vs P-pol understanding
- `CRITICAL_ERROR_DIALOGS_IMPLEMENTATION.md` - Error handling

**Code Files**:
- `utils/led_calibration.py` - S-pol validation (prism detection only)
- `utils/spr_signal_processing.py` - Transmission spectrum analysis

---

## ⚠️ Common Pitfalls

**❌ WRONG**:
```python
# DON'T analyze SPR on individual S or P spectra
s_spectrum = usb.read_intensity()  # in S-mode
find_spr_dip(s_spectrum)  # ❌ WRONG - no SPR in S-pol!
```

**✅ CORRECT**:
```python
# ONLY analyze SPR on transmission spectrum
s_spectrum = measure_s_mode()
p_spectrum = measure_p_mode()
transmission = p_spectrum / s_spectrum * 100.0
find_spr_dip(transmission)  # ✅ CORRECT
```

---

**END OF SERVO CALIBRATION MASTER REFERENCE**
