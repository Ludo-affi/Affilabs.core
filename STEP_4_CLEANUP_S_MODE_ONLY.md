# Step 4 Cleanup: S-Mode Only ✅

## What Changed

**Removed P-mode references from Step 4** to keep calibration focused on S-mode only.

---

## Rationale

### Calibration = S-Mode ONLY

**Steps 1-9 are ALL S-mode (reference measurements)**:
1. Dark noise measurement (S-mode)
2. Wavelength calibration (S-mode)
3. LED brightness ranking (S-mode)
4. **Integration time optimization (S-mode)** ← THIS STEP
5. Fine-tune detector range (S-mode)
6. LED intensity calibration (S-mode)
7. Reference signal measurement (S-mode)
8. P-mode LED adjustment (S-mode reference)
9. Validation (S-mode)

**P-mode is ONLY used for**:
- Live data acquisition (after calibration completes)
- Real-time SPR measurements
- Continuous monitoring

### Integration Time Scaling

**How P-mode integration time is calculated**:
- NOT during calibration
- NOT in Step 4
- **Later**: When entering live mode in state machine
- Uses `LIVE_MODE_INTEGRATION_FACTOR = 0.5`
- Scales S-mode integration time: `p_mode_integration = s_mode_integration × 0.5`

---

## Changes Made

### 1. utils/spr_calibrator.py

**Docstring Updated**:
```python
def _optimize_integration_time(self, weakest_ch: str, integration_step: float) -> bool:
    """STEP 4: Constrained dual optimization for integration time (S-MODE ONLY).

    This optimizes integration time for CALIBRATION (S-mode) only.
    P-mode integration time is calculated later when entering live mode.
    
    ...
    """
```

**Removed P-mode Calculation**:
```python
# REMOVED:
# from settings import LIVE_MODE_INTEGRATION_FACTOR
# p_mode_integration = best_integration * LIVE_MODE_INTEGRATION_FACTOR

# REMOVED:
# logger.info(f"   P-mode (live): {p_mode_integration*1000:.1f}ms (factor={LIVE_MODE_INTEGRATION_FACTOR})")
```

**Enhanced Final Output**:
```python
logger.info(f"")
logger.info(f"="*80)
logger.info(f"✅ INTEGRATION TIME OPTIMIZED (S-MODE)")
logger.info(f"="*80)
logger.info(f"")
logger.info(f"   Optimal integration time: {best_integration*1000:.1f}ms")
logger.info(f"")
logger.info(f"   Weakest LED ({weakest_ch} @ LED=255):")
logger.info(f"      Signal: {best_weakest_signal:6.0f} counts ({weakest_percent:5.1f}%)")
logger.info(f"      Status: ✅ OPTIMAL")
logger.info(f"")
logger.info(f"   Strongest LED ({strongest_ch} @ LED={STRONGEST_MIN_LED}):")
logger.info(f"      Signal: {best_strongest_signal:6.0f} counts ({strongest_percent:5.1f}%)")
logger.info(f"      Status: ✅ Safe (<95%)")
logger.info(f"")
logger.info(f"   Middle LEDs: Automatically within boundaries ✅")
logger.info(f"")
logger.info(f"   This integration time will be used for:")
logger.info(f"      • Step 5: Fine-tune detector range")
logger.info(f"      • Step 6: LED intensity calibration")
logger.info(f"      • Step 7: Reference signal measurement")
logger.info(f"")
logger.info(f"   Note: P-mode integration time is calculated later when entering live mode")
logger.info(f"="*80)
```

### 2. settings/settings.py

**Updated Comments**:
```python
# Step 4 constrained dual optimization targets (S-MODE CALIBRATION ONLY)
# P-mode integration time is calculated later using LIVE_MODE_INTEGRATION_FACTOR
WEAKEST_TARGET_PERCENT = 70  # % - target for weakest LED at LED=255 (maximize SNR for calibration)
WEAKEST_MIN_PERCENT = 60  # % - minimum acceptable for weakest LED during calibration
WEAKEST_MAX_PERCENT = 80  # % - maximum acceptable for weakest LED during calibration
STRONGEST_MAX_PERCENT = 95  # % - saturation threshold for strongest LED at LED≥25 (ensures calibration can succeed)
STRONGEST_MIN_LED = 25  # Minimum practical LED intensity (10% of 255) for strongest LED validation
```

---

## Expected Log Output (Updated)

### Step 4 Final Output

```
================================================================================
✅ INTEGRATION TIME OPTIMIZED (S-MODE)
================================================================================

   Optimal integration time: 150.2ms

   Weakest LED (A @ LED=255):
      Signal: 42,675 counts ( 65.1%)
      Status: ✅ OPTIMAL

   Strongest LED (D @ LED=25):
      Signal: 12,185 counts ( 18.6%)
      Status: ✅ Safe (<95%)

   Middle LEDs: Automatically within boundaries ✅

   This integration time will be used for:
      • Step 5: Fine-tune detector range
      • Step 6: LED intensity calibration
      • Step 7: Reference signal measurement

   Note: P-mode integration time is calculated later when entering live mode
================================================================================
```

**Key Differences**:
- ❌ NO "P-mode (live): 75.1ms" line
- ✅ Clear "S-MODE" in title
- ✅ Usage notes show Steps 5, 6, 7
- ✅ Explicit note about P-mode being handled later

---

## Step 4 Responsibilities (Clarified)

### ✅ What Step 4 DOES

1. **Optimize integration time for S-mode calibration**
   - Maximize weakest LED (60-80% at LED=255)
   - Constrain strongest LED (<95% at LED=25)
   - Ensure integration time ≤200ms

2. **Store optimized integration time**
   - `self.state.integration` for S-mode
   - Used by Steps 5, 6, 7

3. **Validate constraints**
   - Weakest LED in target range
   - Strongest LED safe for calibration
   - Middle LEDs automatically within boundaries

### ❌ What Step 4 DOES NOT DO

1. **Calculate P-mode integration time**
   - This is done later in state machine
   - When transitioning to live mode
   - Uses `LIVE_MODE_INTEGRATION_FACTOR = 0.5`

2. **Apply integration time to live mode**
   - Calibration doesn't interact with live mode
   - State machine handles mode transitions

3. **Store P-mode-specific values**
   - Only S-mode integration is stored
   - P-mode is derived at runtime

---

## Why This Matters

### 1. Single Responsibility Principle
- Step 4: Optimize integration time **for calibration**
- State Machine: Handle integration time **for live mode**
- Clear separation of concerns

### 2. Simpler Code
- No P-mode logic in calibration
- Easier to understand and maintain
- Less coupling between components

### 3. Future-Proof
- If P-mode scaling factor changes (0.5 → 0.4)
- Only need to update state machine
- Calibration code unchanged

### 4. Correct Documentation
- Documentation now accurately reflects what Step 4 does
- No misleading references to P-mode
- Clear about when P-mode integration is calculated

---

## P-Mode Integration Time (For Reference)

**Where is P-mode integration calculated?**

**File**: `utils/spr_state_machine.py`
**Method**: `sync_from_shared_state()`
**When**: After calibration completes, when creating data acquisition wrapper

```python
def sync_from_shared_state(self) -> None:
    """Sync acquisition parameters from shared calibration state."""
    if self.calib_state is None:
        return

    # Get S-mode integration time from calibration
    if self.calib_state.integration > 0:
        from settings import LIVE_MODE_INTEGRATION_FACTOR
        integration_seconds = self.calib_state.integration

        # Scale integration time for live mode (P-mode) to prevent saturation
        live_integration_seconds = integration_seconds * LIVE_MODE_INTEGRATION_FACTOR

        logger.info(
            f"✅ Live mode integration scaled: {integration_seconds*1000:.1f}ms → {live_integration_seconds*1000:.1f}ms (factor={LIVE_MODE_INTEGRATION_FACTOR})"
        )

        # Apply to spectrometer
        if hasattr(self.app, 'usb') and self.app.usb is not None:
            if hasattr(self.app.usb, 'set_integration'):
                self.app.usb.set_integration(live_integration_seconds)
            elif hasattr(self.app.usb, 'set_integration_time'):
                self.app.usb.set_integration_time(live_integration_seconds)
```

**This is SEPARATE from calibration!** ✅

---

## Testing Impact

### No Change to Test Procedure

**Same testing steps**:
1. Delete calibration cache
2. Restart application
3. Run fresh calibration
4. Verify Step 4 logs (now clearer, no P-mode)
5. Test P-mode (same as before)

**Log differences**:
- Step 4: No longer shows P-mode integration
- State machine: Still shows P-mode scaling (unchanged)

---

## Git Commit

```
b140c17 - Step 4: Remove P-mode references - calibration is S-mode only
```

**Commit message**:
```
CLEANUP:
- Step 4 is for S-mode calibration only
- P-mode integration time is calculated LATER when entering live mode
- Removed P-mode calculation from Step 4 optimization
- Updated docstrings and comments to clarify S-mode focus
- Enhanced final log output to show intended usage

RATIONALE:
- Calibration Steps 1-9 are all S-mode (reference measurements)
- P-mode is only used during live data acquisition
- Integration time scaling happens in state machine, not calibration
- Keeps Step 4 focused on its single responsibility
```

---

## Summary

**What we did**:
1. ✅ Removed P-mode calculation from Step 4
2. ✅ Updated docstrings to clarify S-mode only
3. ✅ Enhanced final log output with usage notes
4. ✅ Updated comments in settings.py
5. ✅ Committed and pushed to master

**Why we did it**:
- Step 4 is part of calibration (S-mode only)
- P-mode integration is calculated later (state machine)
- Clearer separation of concerns
- More accurate documentation

**Impact**:
- No functional change (P-mode still works the same)
- Clearer code and documentation
- Easier to understand and maintain

**Result**: Step 4 now correctly reflects its purpose: **S-mode calibration integration time optimization** ✅
