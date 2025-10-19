# Polarizer Physics - Corrected Understanding

**Date**: 2025-10-19
**Status**: ✅ CORRECTED in OEM calibration tool and documentation

## Background

This document clarifies the **correct** physical behavior of the polarizer system based on actual device measurements.

---

## ❌ Previous (Incorrect) Understanding

The original implementation assumed:
- **P-mode (parallel)**: HIGH transmission (~1000 counts)
- **S-mode (perpendicular)**: LOW transmission (~100 counts)

This led to inverted logic in the OEM calibration tool.

---

## ✅ Corrected Physics (User Clarification)

### Actual Polarization Behavior

The servo rotates a polarizer from 10° to 170°. **Most positions BLOCK light** (very low signal ~50-100 counts). Only **two positions** allow significant light transmission:

#### **S-mode (Perpendicular Polarization)**
- **Transmission**: **HIGH** (~1000+ counts)
- **Physical Meaning**: Light passes through with minimal blocking
- **Usage**: Reference signal measurements (Step 7 in calibration)
- **Servo Position**: Typically ~100° (device-specific, determined by OEM calibration)

#### **P-mode (Parallel Polarization)**
- **Transmission**: **LOWER but SUBSTANTIAL** (~300-700 counts)
- **Physical Meaning**: Light is partially attenuated, but **NOT near zero**
- **Usage**: Live SPR measurements (P-mode is sensitive to refractive index changes)
- **Servo Position**: Typically ~10° (device-specific, determined by OEM calibration)

#### **All Other Positions**
- **Transmission**: **Very LOW** (~50-100 counts)
- **Physical Meaning**: Light is blocked by the polarizer
- **Usage**: Not used for measurements

---

## Key Insight: S > P (Not P > S)

### Expected Signal Relationship
```
S-mode intensity > P-mode intensity

Typical ratio: S/P = 3-15× (S is significantly brighter)
Example:
  S-mode: 1000 counts
  P-mode:  300 counts
  Ratio:   3.33×
```

### Why This Matters for OEM Calibration

During the **polarizer servo sweep** (10-170° in 5° steps):

1. **Most measurements will be LOW** (~50-100 counts) - polarizer is blocking light
2. **Two peaks will emerge**:
   - **Higher peak** = S-mode position (maximum transmission)
   - **Lower peak** = P-mode position (reduced but substantial transmission)

3. **Peak Detection** identifies both peaks
4. **Validation** measures actual intensity at each position to confirm:
   - Which position gives HIGH signal → Label as **S**
   - Which position gives LOWER signal → Label as **P**

5. **Label Verification**:
   - If hardware labels match physics → ✅ LABELS CORRECT
   - If hardware labels are inverted → ⚠️ LABELS INVERTED (swap needed)

---

## Impact on Software

### OEM Calibration Tool (`utils/oem_calibration_tool.py`)
✅ **UPDATED** (2025-10-19):
- Corrected peak identification logic
- S-mode = HIGHER transmission peak
- P-mode = LOWER transmission peak
- Proper S/P ratio calculation (S/P, not P/S)
- Updated documentation and comments

### Main Calibration (`utils/spr_calibrator.py`)
✅ **ALREADY CORRECT**:
- `validate_polarizer_positions()` measures actual intensities
- Swaps labels if hardware is inverted
- Applies corrected positions to hardware via `servo_set()`

### Transmission Graph Behavior
✅ **EXPECTED**:
- Reference (S-mode): HIGH baseline (~1000 counts)
- Live (P-mode): LOWER signal (~300-700 counts)
- **Transmission = Live/Reference**
- When SPR binding occurs: P-mode signal **DECREASES** → Transmission **DROPS**
- Graph should show **DIP** during binding events

---

## Validation Criteria

### OEM Calibration Success Criteria

1. **Two Distinct Peaks Found**
   - Peak detection identifies exactly 2 peaks
   - Peaks are well-separated (>20° apart)

2. **S/P Ratio Check**
   - S-mode intensity > P-mode intensity
   - Ratio S/P > 3.0× (ideally 5-15×)
   - If ratio < 2.0× → ⚠️ Warning (polarizer may be misaligned)

3. **P-mode Not Near Zero**
   - P-mode intensity should be substantial (>100 counts)
   - If P-mode < 100 counts → ⚠️ Warning (check alignment)

4. **Label Verification**
   - Hardware labels checked against physical behavior
   - If inverted: Labels swapped in software AND applied to hardware

---

## Example OEM Calibration Output

```
================================================================================
POLARIZER CALIBRATION RESULTS:
================================================================================
✅ LABELS CORRECT  (or ⚠️ LABELS INVERTED)
Actual S position (HIGH transmission): 100° → 1050 counts
Actual P position (LOW transmission):   10° →  315 counts
S/P intensity ratio: 3.33× (expected > 3.0)
================================================================================
```

---

## References

- User clarification: 2025-10-19
- OEM Tool: `utils/oem_calibration_tool.py`
- Validation: `utils/spr_calibrator.py::validate_polarizer_positions()`
- Documentation: `OEM_CALIBRATION_TOOL_GUIDE.md`

---

## Summary

**S-mode** transmits **MORE** light than **P-mode**.
P-mode is **NOT near zero** - it's reduced but substantial.
Most servo positions **BLOCK** light completely.

This is now correctly implemented in the OEM calibration tool and all documentation.
