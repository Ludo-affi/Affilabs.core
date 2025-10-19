# Transmission Calculation Fix - Inverted Formula

**Date**: 2025-10-19
**Issue**: Transmission graph shows PEAK instead of DIP
**Root Cause**: Formula is inverted

---

## Current (WRONG) Formula

```python
transmission = (P_live / S_ref) × 100
```

**Problem**:
- Step 7: Measures reference in **S-mode** (HIGH signal ~1000 counts)
- Live: Measures in **P-mode** (LOWER signal ~300-700 counts)
- Result: `300 / 1000 = 30%` → **LOW baseline** (wrong!)
- On SPR binding: P decreases → `200 / 1000 = 20%` → Shows **DIP** (could be correct if baseline was high)

---

## Corrected Formula

```python
transmission = (S_ref / P_live) × 100
```

**Why This Works**:
- Step 7: Reference in **S-mode** (HIGH signal ~1000 counts)
- Live: Measures in **P-mode** (LOWER signal ~300-700 counts)
- Result: `1000 / 300 = 333%` → **HIGH baseline** (correct!)
- On SPR binding: P decreases → `1000 / 200 = 500%` → Shows **PEAK** (correct!)

---

## Alternative: Swap Modes (More Complex)

Instead of inverting the formula, could swap which mode is used where:

- Step 7: Measure reference in **P-mode** (HIGH)
- Live: Measure in **S-mode** (LOW)
- Formula: `P_ref / S_live`
- Baseline: `1000 / 300 = 333%`
- On binding: S decreases → `1000 / 200 = 500%` → PEAK

**BUT**: This requires changing calibration (Step 7) and live acquisition - more risky!

---

## Recommended Fix: Invert Formula Only

**File to modify**: `utils/spr_data_processor.py`

**Line ~206**:
```python
# OLD (WRONG):
transmission = (p_pol_corrected / s_ref_corrected) * 100.0

# NEW (CORRECT):
transmission = (s_ref_corrected / p_pol_corrected) * 100.0
```

This is a **1-line fix** that inverts the transmission calculation.

---

## Expected Behavior After Fix

| Condition | P-mode (live) | S-mode (ref) | Transmission | Graph |
|-----------|---------------|--------------|--------------|-------|
| Baseline | 300 counts | 1000 counts | 333% | HIGH baseline |
| SPR binding starts | 250 counts | 1000 counts | 400% | PEAK ↑ |
| SPR saturation | 200 counts | 1000 counts | 500% | MAX PEAK |
| Dissociation | 300 counts | 1000 counts | 333% | Returns to baseline |

Graph shape: **HIGH baseline** → **PEAK on binding** → **Return to baseline**

---

## Why User Sees Inverted Graph

Currently:
- Baseline: `P/S = 300/1000 = 30%` (LOW)
- Binding: `P/S = 200/1000 = 20%` (LOWER - DIP)

User expects:
- Baseline: HIGH
- Binding: PEAK

The formula is mathematically inverted!

---

## Implementation

Apply the 1-line fix to `spr_data_processor.py` line ~206.

