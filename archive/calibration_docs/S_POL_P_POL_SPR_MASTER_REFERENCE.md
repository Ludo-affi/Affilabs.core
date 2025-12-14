# S-Pol and P-Pol Master Reference for SPR Systems

**AUTHORITATIVE DOCUMENTATION - Last Updated: November 23, 2025**

This document is the single source of truth for understanding S-polarization and P-polarization in the Affilabs SPR system.

---

## ⚠️ CRITICAL: Correct Understanding of S-Pol vs P-Pol

### Physical Reality

**S-Polarization (Reference Mode)**
- **Purpose**: LED spectral profile characterization + detector performance baseline
- **What it measures**: Light transmission WITHOUT SPR interaction
- **Contains**: LED emission spectrum, optical path losses, detector response
- **Does NOT contain**: ANY SPR information (no dip, no resonance)
- **Signal characteristics**: HIGH intensity, FLAT spectrum (no dip)
- **Use case**: Denominator in transmission calculation (normalizes out LED/detector effects)

**P-Polarization (SPR-Active Mode)**
- **Purpose**: Measures light AFTER SPR interaction with sensor
- **What it measures**: Light transmission WITH SPR absorption
- **Contains**: Same LED profile + optical losses + SPR dip
- **Signal characteristics**: LOWER intensity than S-pol, shows SPR dip (reduced transmission)
- **Use case**: Numerator in transmission calculation

**Transmission Spectrum (P/S Ratio)**
- **Calculation**: `Transmission = (P-pol / S-pol) × 100%`
- **Result**: Isolates ONLY the SPR effect by dividing out LED profile and detector response
- **Shows**: SPR absorption dip (transmission reduction at resonance wavelength)
- **This is the ONLY spectrum where SPR dip/FWHM analysis applies**

---

## 📊 Analysis Rules (MUST FOLLOW)

### ✅ ALLOWED Operations

**On S-Pol Spectrum:**
- ✅ Check signal intensity (prism presence detection)
- ✅ Measure LED spectral profile
- ✅ Validate signal level for saturation
- ✅ Assess detector performance

**On P-Pol Spectrum:**
- ✅ Check signal intensity
- ✅ Compare to S-pol (but NOT for SPR analysis)
- ✅ Validate signal level for saturation

**On Transmission Spectrum (P/S ratio):**
- ✅ Find SPR dip (minimum transmission)
- ✅ Measure FWHM (dip width)
- ✅ Calculate dip depth
- ✅ Track resonance wavelength
- ✅ Analyze SPR coupling quality

### ❌ FORBIDDEN Operations

**NEVER analyze SPR dip/FWHM on individual S or P spectra:**
- ❌ NEVER look for SPR dip in S-pol (it doesn't exist!)
- ❌ NEVER analyze FWHM on S-pol
- ❌ NEVER analyze dip depth on S-pol
- ❌ NEVER perform SPR analysis on P-pol alone

**The ONLY valid SPR analysis is on transmission spectrum (P/S ratio)**

---

## 🔬 Water Detection Capabilities

### At S-Pol Stage
- ✅ **Can detect**: Prism presence/absence (by signal intensity)
- ❌ **Cannot detect**: Water presence (no SPR information available)
- **Method**: Compare signal intensity to expected baseline

### At P-Pol Stage
- ✅ **Can detect**: Water presence on sensor (SPR dip appears)
- **Method**: Calculate transmission spectrum (P/S ratio) and analyze for SPR dip
- **Requirement**: Must have transmission dip depth >10% and wavelength 590-670nm

---

## 🎯 Servo/Polarizer Calibration

### When Servo Calibration Runs

Servo calibration is part of the **initial device setup sequence**:

```
1. Connect Hardware → Device identified
2. Load device_config.json → Check for servo positions
3. Decision Point:
   • If servo positions EXIST → Skip to LED calibration (fast path)
   • If servo positions MISSING → Run servo calibration (method below)
4. LED Calibration → Common path (same for all polarizer types)
```

**Key Point**: Servo calibration is **only required once** during initial setup or after hardware changes. Once servo positions are stored in device_config.json, the system uses them for all future sessions and proceeds directly to LED calibration.

### Circular Polarizers (Standard Devices)

**Method**: Intelligent Quadrant Search
- Phase 1: 5-point coarse search across servo range (10-170°)
- Phase 2: Refinement around P position (minimum intensity = strongest SPR absorption)
- Phase 3: S calculated exactly 90° away from P (enforced by physics)
- **ROI**: 600-750nm (SPR resonance region)
- **Validation**: Transmission dip depth >10%, wavelength 590-670nm, S/P ratio >1.3×
- **Requirement**: Water on sensor (for SPR detection)
- **Measurements**: ~13 positions (vs 33+ for full sweep)

**Location**: `Affilabs.core beta/utils/servo_calibration.py::perform_quadrant_search()`

### Barrel Polarizers (Discrete Windows)

**Method**: Window Detection with SPR Signature Identification

Barrel polarizers have ONLY 2 physical windows (not continuous rotation):
- Each window spans multiple servo positions (cluster of high transmission)
- Windows separated by >70° (typically ~90°)
- One window has S-pol film strip, other has P-pol film strip

**Algorithm**:
1. **Full sweep** to find ALL transmission peaks
2. **Cluster peaks** into 2 window groups (separated by >70°)
3. **Find center** of each window (max transmission in cluster)
4. **Identify S vs P** using SPR signature:
   - **S window**: High transmission, minimal SPR effect (reference)
   - **P window**: Lower transmission, shows SPR dip when water present
5. **Validate** separation >70° and S/P ratio >1.3×

**Location**: `Affilabs.core beta/utils/servo_calibration.py::perform_barrel_window_search()`

**Key Difference from Circular**:
- Does NOT require water for window detection (can find windows by intensity alone)
- Windows are NOT exactly 90° apart (physical constraint of barrel design)
- Must identify which window is S vs P (not predetermined by 90° offset)

---

## 💾 Calibration Save Flow

### CORRECT Flow (As Implemented)

```
1. Auto-calibrate polarizer
   ↓
2. Return results for USER CONFIRMATION
   - Show: S position, P position, S/P ratio, dip depth, resonance wavelength
   - User decides: Accept / Retry / Cancel
   ↓
3. If accepted: Save to device_config.json
   - Updates device configuration file
   - Applies positions to hardware: ctrl.servo_set(s_pos, p_pos)
   ↓
4. Later: User clicks "Push to EEPROM" button
   - Syncs ENTIRE device_config → EEPROM
   - Makes device truly portable
```

**Key Points**:
- ❌ Never auto-save directly to EEPROM
- ✅ Always save to device_config first
- ✅ Always require user confirmation before saving
- ✅ EEPROM sync is separate, manual operation for full config backup

---

## 📂 File Locations

### Active Implementation Files

**Servo Calibration (NEW - Correct Implementation)**:
- `Affilabs.core beta/utils/servo_calibration.py` ← **MASTER FILE**
  - `auto_calibrate_polarizer()` - Main entry point (supports circular & barrel)
  - `perform_quadrant_search()` - Circular polarizer method
  - `perform_barrel_window_search()` - Barrel polarizer method
  - `validate_positions_with_transmission()` - Transmission-based validation
  - `check_water_presence()` - Water detection via transmission

**SPR Calibrator Integration**:
- `utils/spr_calibrator.py::auto_polarize()` - Wrapper that calls servo_calibration module

**LED Calibration (S-Pol Understanding)**:
- `utils/led_calibration.py`
  - `validate_s_ref_quality()` - PRISM PRESENCE ONLY (no SPR analysis)
  - `verify_calibration()` - WATER DETECTION via transmission (P-pol stage)

**Signal Processing (Transmission Analysis)**:
- `utils/spr_signal_processing.py`
  - `validate_sp_orientation()` - Analyzes transmission spectrum (600-750nm ROI)
  - `calculate_transmission()` - P/S ratio calculation

### Deprecated/Archive Files

**Old Software (Reference Only)**:
- `Old software/utils/servo_calibration.py` - Original implementation (reference)
- `Old software/test_servo_calibration.py` - Test script (not used)

---

## 🚫 Raw S vs P Intensity Comparison

**IMPORTANT**: Raw S-pol vs P-pol intensity comparison is ONLY used in ONE place:

**Servo Calibration ONLY**:
- During auto_polarize/servo calibration, we compare raw S and P intensities
- This is to find optimal window positions for maximum light transmission
- This is NOT SPR analysis - it's just finding where light comes through best

**Everywhere else**: Use transmission spectrum (P/S ratio) for ANY SPR-related analysis

---

## 📖 Related Documentation

**Updated Documentation** (Correct understanding):
- This file (S_POL_P_POL_SPR_MASTER_REFERENCE.md) ← YOU ARE HERE
- `CRITICAL_ERROR_DIALOGS_IMPLEMENTATION.md` - Error handling for calibration failures

**Outdated Documentation** (DO NOT USE - Contains incorrect S-pol SPR analysis):
- ❌ `docs/POLARIZER_REFERENCE.md` - **OUTDATED** (contradicts correct understanding)
- ❌ `docs/calibration/POLARIZER_CALIBRATION_SYSTEM.md` - **OUTDATED** (incorrect algorithm description)
- ❌ Root directory POLARIZER_*.md files - **MIXED** (some sections outdated)

---

## 🔄 Version History

**v1.0 - November 23, 2025**
- Initial master reference created
- Consolidated correct S-pol/P-pol understanding
- Documented circular vs barrel polarizer methods
- Clarified servo calibration and save flow
- Marked outdated documentation for cleanup

---

## ✅ Quick Reference Card

| Aspect | S-Pol | P-Pol | Transmission (P/S) |
|--------|-------|-------|-------------------|
| **Purpose** | LED reference | SPR measurement | SPR isolation |
| **Contains SPR?** | ❌ NO | ✅ YES | ✅ YES (isolated) |
| **Intensity** | HIGH | LOWER | <100% (dip) |
| **SPR Analysis?** | ❌ NEVER | ❌ NEVER | ✅ ONLY HERE |
| **Water Detection?** | ❌ NO | ✅ YES (via trans) | ✅ YES |
| **Prism Detection?** | ✅ YES | ✅ YES | ❌ NO |
| **Dip/FWHM Analysis?** | ❌ FORBIDDEN | ❌ FORBIDDEN | ✅ ONLY HERE |

---

**END OF MASTER REFERENCE**
