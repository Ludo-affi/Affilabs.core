# File Corruption Fix Complete ✅

## Problem
The file `src/utils/calibration_6step.py` became corrupted during multiple attempts to remove old optimization loop code. The corruption included:
- 312 lines of orphaned indented code (lines 1047-1359)
- Duplicate P-ref capture blocks
- `break` statements outside loops (syntax errors)
- References to undefined variables (`p_iteration`, `P_MODE_LED_TARGET_MIN`)
- Multiple "Capturing P-mode reference" messages

## Root Cause
Multiple incomplete `replace_string_in_file` operations left scattered junk code fragments instead of cleanly removing the old while loop.

## Solution Applied
**Single atomic deletion**: Removed all corrupt code (lines 1047-1359) in one operation.

### File Structure (After Fix)
```
Lines 1040-1046: ✅ P-ref capture block (KEPT - correct)
Lines 1047-1050: ✅ 3-Parameter Assessment header (CLEAN)
Lines 1051+:     ✅ Complete 3-parameter assessment code (KEPT - correct)
```

## Verification
- ✅ Syntax check passed: `python -m py_compile calibration_6step.py`
- ✅ File reduced from 2110 lines to 1798 lines (-312 corrupt lines)
- ✅ No orphaned code fragments
- ✅ No duplicate blocks
- ✅ All control flow statements properly nested

## What Was Fixed
The 3-parameter assessment system now runs cleanly:

### Assessment Logic (AFTER P-ref capture)
1. **Signal counts**: Checks if `p_weakest_signal_counts < 45,000` (target: 53,099)
2. **LED intensity**: Checks if `p_weakest_led >= 250` (maxed out?)
3. **Integration time**: Checks if `integration_time >= 100` (at limit?)

### Decision Logic
- **needs_optimization**: Signal below target (< 45K counts)
- **can_optimize**: LED or integration has headroom
- **IF** needs_optimization AND can_optimize → **THEN** optimize

## Expected Behavior (Next Calibration)
For channels A & D with weak signals:
```
✅ P-mode references captured
📊 P-MODE 3-PARAMETER OPTIMIZATION ASSESSMENT
PARAMETER 1: Signal Counts
   Ch A: 31046 counts (LED=255) [58.4% of target]
   Ch D: 30219 counts (LED=255) [56.9% of target]
   Weakest: Ch A at 31046 counts
   Target: 53099 counts
   Deficit: 22053 counts (41.5%)

PARAMETER 2: LED Intensity
   Ch A: LED=255/255 (maxed out)
   Ch D: LED=255/255 (maxed out)
   Weakest LED: Ch A at 255/255
   → MAXED OUT (no LED headroom)

PARAMETER 3: Integration Time
   Current: 36ms / 100ms max
   Headroom: 64ms (177% increase possible)
   → CAN INCREASE integration time

DECISION: ✅ Optimization needed AND possible
   Signal: 41.5% below target
   LED: Maxed out (no headroom)
   Integration: Can increase by 177%
   → STRATEGY: Increase integration time to boost signal

ITERATION #1: Increasing integration 36→43ms (+20%)
[Re-optimize P-mode LEDs, recapture P-ref]
[Repeat until target reached or limits hit]
```

## Ready for Testing
The file is now clean and ready to test calibration on the user's device.

**Next Step**: Run calibration and verify the optimization triggers for channels A & D.

---
**File**: `src/utils/calibration_6step.py`
**Lines removed**: 312 corrupt lines (1047-1359)
**Final line count**: 1798 lines
**Status**: ✅ CLEAN, ✅ SYNTAX VALID, ✅ READY FOR TESTING
