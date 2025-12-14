# SPR Signal Orientation - AUTHORITATIVE CLARIFICATION

**Date**: November 30, 2025
**Status**: ✅ CONFIRMED CORRECT

---

## 🔬 Physical Reality (CONFIRMED)

### S-Polarization (Reference Channel)
- **Signal Level**: HIGH intensity
- **SPR Behavior**: NO SPR dip present
- **Purpose**: Reference beam - measures LED spectral profile without SPR interaction
- **Characteristics**: Smooth, flat spectrum at high intensity
- **Servo Position**: Where maximum light transmission occurs

### P-Polarization (Measurement Channel)
- **Signal Level**: LOWER intensity (compared to S)
- **SPR Behavior**: Shows SPR dip (resonance absorption)
- **Purpose**: Measurement beam - SPR interaction reduces transmission at resonance wavelength
- **Characteristics**: Lower intensity with characteristic dip in SPR region (590-670nm)
- **Servo Position**: Where minimum light transmission occurs (90° from S for circular polarizers)

### Transmission Spectrum (P/S Ratio)
- **Calculation**: `Transmission = (P / S) × 100%`
- **Result**: Shows SPR dip (where P is reduced relative to S)
- **This is where SPR analysis happens**: dip detection, FWHM calculation, resonance tracking

---

## ✅ Code Implementation Status

### Servo Calibration (CORRECT ✅)
Location: `src\utils\servo_calibration.py`

```python
# Line 386-390: Search for S position (MAXIMUM)
logger.info("STEP 2: Coarse quadrant search for S position (maximum transmission)...")
logger.info("   Searching in S-mode (parallel to analyzer) - strongest signal")

# Line 508-510: Search for P position (MINIMUM)
logger.info(f"STEP 4: Finding P position (minimum) at S ± 90 servo units...")
# ...
p_pos_servo = min(p_measurements.keys(), key=lambda k: p_measurements[k])
```

**Implementation**: ✅ **CORRECT**
- S position = Maximum intensity (HIGH transmission)
- P position = Minimum intensity (SPR absorption)
- S/P ratio > 1.0 (S is higher than P)

### SPR Calibrator Validation (CORRECT ✅)
Location: `utils\spr_calibrator.py`

```python
# Lines 2296-2312: Validate P < S
logger.info(f"   S-mode intensity: {s_max:.1f} counts (HIGH expected - reference)")
logger.info(f"   P-mode intensity: {p_max:.1f} counts (LOWER expected - resonance)")
logger.info(f"   Measured P/S ratio: {ratio:.3f} (expect < 1.0)")

# Lines 2329-2334: Check P/S ratio
MAX_RATIO = 0.95  # Maximum ratio (P should be clearly lower than S)
IDEAL_RATIO_MAX = 0.75  # Ideal upper bound
IDEAL_RATIO_MIN = 0.10   # Ideal lower bound (P not too weak)
```

**Implementation**: ✅ **CORRECT**
- Expects P/S ratio < 1.0 (P is LOWER than S)
- Validates that S has HIGH intensity (reference)
- Validates that P has LOWER intensity (SPR absorption)

### Documentation (CORRECT ✅)
Location: `docs\S_POL_P_POL_SPR_MASTER_REFERENCE.md`

```markdown
**S-Polarization (Reference Mode)**
- Signal characteristics: HIGH intensity, FLAT spectrum (no dip)

**P-Polarization (SPR-Active Mode)**
- Signal characteristics: LOWER intensity than S-pol, shows SPR dip
```

**Documentation**: ✅ **CORRECT**
- S = HIGH intensity, no dip
- P = LOWER intensity, has dip

---

## 📊 Quick Reference Table

| Aspect | S-Pol | P-Pol | Transmission (P/S) |
|--------|-------|-------|--------------------|
| **Signal Level** | HIGH ⬆️ | LOWER ⬇️ | <100% (dip) |
| **SPR Dip** | ❌ NO | ✅ YES | ✅ YES (isolated) |
| **Servo Position** | Maximum transmission | Minimum transmission | N/A |
| **P/S Intensity Ratio** | Denominator (1.0) | Numerator (<1.0) | <1.0 |
| **SPR Analysis** | ❌ NEVER | ❌ NEVER | ✅ ONLY HERE |

---

## 🎯 Common Confusion Points (CLARIFIED)

### ❓ "Which channel shows the SPR dip?"
**Answer**: Neither S nor P individually shows an SPR dip in the raw spectrum.
- S channel: High, flat reference spectrum
- P channel: Lower spectrum due to SPR absorption
- **Transmission (P/S)**: Shows the dip where P is reduced relative to S

### ❓ "Why is S higher than P?"
**Answer**: P-polarization interacts with the SPR sensor, causing resonance absorption.
- At resonance wavelength (~630nm): P intensity drops significantly
- S-polarization doesn't interact with SPR, maintains high transmission
- Result: S > P, ratio P/S < 1.0

### ❓ "Where do I measure FWHM?"
**Answer**: ONLY on the transmission spectrum (P/S ratio), NEVER on S or P alone.
- Transmission spectrum isolates the SPR effect
- Shows characteristic dip shape with measurable FWHM
- Removes LED spectral profile and detector response variations

---

## 🚨 CRITICAL: What NOT To Do

### ❌ NEVER:
1. Look for SPR dip in S-channel (it doesn't exist!)
2. Analyze FWHM on S-channel
3. Analyze dip depth on S-channel
4. Perform SPR analysis on P-channel alone
5. Compare raw S vs P intensities for SPR quality (use transmission only)

### ✅ ALWAYS:
1. Use S as reference (denominator in transmission calculation)
2. Use P as measurement (numerator in transmission calculation)
3. Analyze SPR features on transmission spectrum (P/S ratio)
4. Expect S > P in intensity (ratio < 1.0)
5. Validate that S is high and flat (good reference quality)

---

## 📝 Summary

**The current implementation and documentation are CORRECT.**

- **S**: High intensity reference, no SPR dip
- **P**: Lower intensity measurement, SPR absorption present
- **Transmission (P/S)**: Where SPR dip is visible and analyzed

This document confirms the physical understanding and validates that the code implements it correctly.

---

**END OF CLARIFICATION**
