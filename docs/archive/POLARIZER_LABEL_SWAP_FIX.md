# Polarizer Position Label Swap Fix

## Issue Identified

**Problem**: The hardware servo positions for S and P modes were **LABELED incorrectly**, causing saturation and incorrect calibration behavior.

### Physical Reality vs. Software Labels

**What was happening**:
- Hardware position labeled "S" (10°) → Actually produces **HIGH transmission** (P-mode behavior)
- Hardware position labeled "P" (100°) → Actually produces **LOW transmission** (S-mode behavior)

**Expected behavior in TRANSMISSION mode**:
- **P-mode** (parallel polarization): HIGH transmission, light passes through
- **S-mode** (perpendicular polarization): LOW transmission, light blocked

## Root Cause

During OEM setup, polarizers are physically installed and the servo positions are found. However:
1. The **servo positions** (10° and 100°) are **HARDWARE-SPECIFIC** - these don't change
2. The **LABELS** (which position is "S" vs "P") depend on **physical polarizer orientation**
3. This particular device had **labels SWAPPED** - position 10° was labeled "S" but behaves like "P"

## Solution Implemented

### Position Label Swapping (Not Hardware Commands!)

**File**: `utils/spr_calibrator.py`

**Changes in `validate_polarizer_positions()`**:

```python
# BEFORE (incorrect labels):
current_positions = self.ctrl.servo_get()
s_position = int(current_positions["s"].decode())  # Gets 10°
p_position = int(current_positions["p"].decode())  # Gets 100°
self.state.polarizer_s_position = s_position  # Stores 10° as S (WRONG!)
self.state.polarizer_p_position = p_position  # Stores 100° as P (WRONG!)

# AFTER (corrected labels):
current_positions = self.ctrl.servo_get()
s_hardware = int(current_positions["s"].decode())  # Gets 10° (HW label)
p_hardware = int(current_positions["p"].decode())  # Gets 100° (HW label)

# ⚠️ SWAP LABELS: Hardware labels are INVERTED
# What hardware calls "S" is actually the P position (HIGH transmission)
# What hardware calls "P" is actually the S position (LOW transmission)
self.state.polarizer_s_position = p_hardware  # S-mode uses 100° (LOW)
self.state.polarizer_p_position = s_hardware  # P-mode uses 10° (HIGH)
```

### Updated Default Values

**Changed defaults throughout the codebase**:

```python
# OLD defaults (incorrect):
polarizer_s_position = 10   # S at 10° (WRONG - this gives HIGH signal)
polarizer_p_position = 100  # P at 100° (WRONG - this gives LOW signal)

# NEW defaults (corrected):
polarizer_s_position = 100  # S at 100° (CORRECT - LOW transmission)
polarizer_p_position = 10   # P at 10° (CORRECT - HIGH transmission)
```

### Files Modified

1. **`utils/spr_calibrator.py`** (3 locations):
   - `validate_polarizer_positions()`: Swap labels when reading from hardware
   - `save_profile()`: Use swapped defaults (S=100°, P=10°)
   - `load_profile()`: Use swapped defaults when loading old profiles

## What This Fix Does

### Validation Flow (Step 2B)

**Before Fix**:
```
Hardware servo_get() → {"s": "010", "p": "100"}
Store: polarizer_s_position = 10°, polarizer_p_position = 100°
Measure P-mode at 100° → LOW signal (saturation when LED compensates!)
Measure S-mode at 10° → HIGH signal (inverted!)
Ratio: S/P = 10/1000 = 0.01 (FAIL - backwards!)
```

**After Fix**:
```
Hardware servo_get() → {"s": "010", "p": "100"}
SWAP LABELS
Store: polarizer_s_position = 100°, polarizer_p_position = 10°
Measure P-mode at 10° (via "ss" cmd) → HIGH signal ✅
Measure S-mode at 100° (via "sp" cmd) → LOW signal ✅
Ratio: P/S = 1000/100 = 10.0 (PASS - correct!)
```

### Calibration Impact

**Step 7 (Reference Signal Measurement)**:
- Now measures in **CORRECT S-mode** (low transmission)
- LED calibration balances correctly without saturation

**Live Measurements**:
- P-mode uses position 10° → High intensity (correct!)
- S-mode uses position 100° → Low intensity for reference (correct!)

## Important Notes

### What We DON'T Change

❌ **Hardware commands remain unchanged**:
- `ss\n` → Still moves to what hardware calls "S position"
- `sp\n` → Still moves to what hardware calls "P position"

❌ **Servo physical positions unchanged**:
- 10° and 100° are still the physical servo angles
- These are hardware-specific and don't change

### What We DO Change

✅ **Software labels for the positions**:
- What we call "S-mode position" in software = 100° (what HW calls "P")
- What we call "P-mode position" in software = 10° (what HW calls "S")

✅ **Stored calibration data**:
- Profiles now save: `polarizer_s_position: 100, polarizer_p_position: 10`
- This ensures correct positions used during live measurements

## Testing Verification

To verify the fix works:

```python
# Run calibration and check Step 2B logs:
# Expected output:
#   Hardware servo positions: labeled-S=10°, labeled-P=100°
#   Corrected positions: S=100° (LOW), P=10° (HIGH)
#   P-mode intensity: ~1000 counts (HIGH expected) ✅
#   S-mode intensity: ~100 counts (LOW expected) ✅
#   P/S ratio: 10.00x ✅ VALIDATED

# Check calibration profile JSON:
{
  "polarizer_s_position": 100,  // Correct: S at 100° (LOW)
  "polarizer_p_position": 10,   // Correct: P at 10° (HIGH)
  "polarizer_sp_ratio": 10.0    // Correct: P/S ratio > 2.0
}
```

## Why This Matters

### Without This Fix
- ❌ Calibration uses **WRONG polarization states**
- ❌ LED intensities compensate incorrectly → **saturation**
- ❌ Reference signals measured in **wrong mode**
- ❌ Live measurements have **inverted polarization**

### With This Fix
- ✅ Calibration uses **CORRECT polarization states**
- ✅ LED intensities balanced properly → **no saturation**
- ✅ Reference signals in proper **S-mode** (low transmission)
- ✅ Live measurements in proper **P-mode** (high transmission)

## Backward Compatibility

**Old calibration profiles** (before fix):
- Used: `polarizer_s_position: 10, polarizer_p_position: 100` (incorrect)
- When loaded: Defaults override with `S=100, P=10` (corrected)
- **Impact**: Old profiles will be corrected automatically

**New calibration profiles** (after fix):
- Store: `polarizer_s_position: 100, polarizer_p_position: 10` (correct)
- When loaded: Positions applied correctly to hardware

## Summary

| Component | Before Fix | After Fix |
|-----------|-----------|-----------|
| **Hardware "S" label** | 10° → Used for S-mode (wrong) | 10° → **Used for P-mode** (correct) |
| **Hardware "P" label** | 100° → Used for P-mode (wrong) | 100° → **Used for S-mode** (correct) |
| **Software S position** | 10° (HIGH signal) ❌ | **100° (LOW signal)** ✅ |
| **Software P position** | 100° (LOW signal) ❌ | **10° (HIGH signal)** ✅ |
| **Calibration result** | Saturation, inverted | **Balanced, correct** ✅ |

**Result**: ✅ Polarizer labels now match physical behavior, preventing saturation and ensuring correct polarization states.
