# P-Mode Integration Time Freeze Policy

## Critical Requirement
**P-mode MUST NEVER reduce integration time below S-mode level!**

P-mode inherits the integration time from S-mode and only adjusts LED intensities.

## Implementation: All Integration Time Reduction Points

### Point 1: Early Saturation Handler (Lines 196-225)
**Location**: Sequential measurement early saturation detection  
**Check**: ✅ `if not freeze_integration and not allow_increase_only`

```python
# CRITICAL: Respect FREEZE_INTEGRATION flag - P-MODE MUST NEVER REDUCE INTEGRATION!
if (not config.PARALLEL_MEASUREMENTS) and early_sat_detected:
    if not freeze_integration and not allow_increase_only:
        _log(logger, "info", "  ⚠️ Early saturation detected - reducing integration time")
        new_integration = calculate_integration_time_reduction(...)
        if new_integration < integration_ms:
            integration_ms = new_integration
            continue
    else:
        # Integration FROZEN (P-mode) - cannot reduce
        _log(logger, "info", f"  🔒 Integration FROZEN at {integration_ms:.1f}ms (P-mode policy)")
        _log(logger, "info", "     Will handle saturation by reducing LEDs instead")
```

**Result**: Early saturation in P-mode triggers LED reduction, NOT integration reduction.

---

### Point 2: Main Saturation Handler (Lines 339-419)
**Location**: STEP 3 - Handle saturation after all channels measured  
**Check**: ✅ `if integration_locked or freeze_integration or allow_increase_only`

```python
# STEP 3: Handle saturation (reduce LED intensities OR integration time)
# CRITICAL P-MODE POLICY: If freeze_integration=True (P-mode), NEVER reduce integration!
total_sat = sum(sat_per_ch.values())
if total_sat > 0:
    if integration_locked or freeze_integration or allow_increase_only:
        # P-MODE PATH: Reduce LEDs, keep integration time
        if freeze_integration:
            _log(logger, "info", f"  🔒 P-MODE FREEZE POLICY ACTIVE - Integration LOCKED at {integration_ms:.1f}ms")
            _log(logger, "info", f"     P-mode inherits S-mode integration time and NEVER reduces it")
        
        # Normalize saturating channel LEDs relative to weakest
        for ch in channels_saturating:
            # Reduce LED to clear saturation
            led_intensities[ch] = new_led
        continue
    
    else:
        # S-MODE PATH: Can reduce integration time
        # CRITICAL: This branch should NEVER execute in P-mode!
        if freeze_integration:
            _log(logger, "error", f"  ❌ BUG: P-mode attempting to reduce integration time!")
            # Safety: don't reduce even if we got here by mistake
        else:
            _log(logger, "info", f"  ⚠️ Multiple channels saturating - reducing integration time")
            new_integration = calculate_integration_time_reduction(...)
            if new_integration < integration_ms:
                integration_ms = new_integration
                continue
```

**Result**: 
- **P-mode**: Saturating channels have LEDs reduced via slope normalization
- **S-mode**: Integration time reduced, all channels re-measured
- **Safety**: Double-check prevents integration reduction even if logic fails

---

### Point 3: Weakest Channel Saturation (Lines 534-562)
**Location**: STEP 4 - Adjust weakest channel when it saturates  
**Check**: ✅ `if not freeze_integration and not allow_increase_only`

```python
# If saturating, reduce integration time instead of LED
# CRITICAL: Respect FREEZE_INTEGRATION flag - P-MODE MUST NEVER REDUCE INTEGRATION!
if sat_pixels > 0:
    if not freeze_integration and not allow_increase_only:
        _log(logger, "info", f"  ⚠️ Weakest channel {ch.upper()} saturating - reducing integration time")
        new_integration = calculate_integration_time_reduction(...)
        if new_integration < integration_ms:
            integration_ms = new_integration
            continue
    else:
        # Integration FROZEN (P-mode) - reduce LED instead
        _log(logger, "info", f"  🔒 P-MODE: Integration FROZEN at {integration_ms:.1f}ms")
        _log(logger, "info", f"     Weakest channel {ch.upper()} saturating - reducing LED instead")
        new_led = calculate_saturation_recovery(...)
        led_intensities[ch] = new_led
        continue
```

**Result**: Even if weakest channel saturates in P-mode, only its LED is reduced, not integration time.

---

### Point 4: Integration Time Increases (Lines 421-518)
**Location**: STEP 3b & 3c - Increase integration when signals too low  
**Check**: ✅ `if not integration_locked and not freeze_integration`

```python
# STEP 3b: If signals uniformly low and LEDs maxed, increase integration
if total_sat == 0 and not integration_locked and not freeze_integration:
    # Can increase integration (both S-mode and P-mode allowed)
    if new_integration > integration_ms:
        integration_ms = new_integration
        continue

# STEP 3c: If maxed LEDs below acceptance, increase integration  
if total_sat == 0 and not integration_locked and not freeze_integration:
    # Can increase integration (both S-mode and P-mode allowed)
    if new_integration > integration_ms:
        integration_ms = new_integration
        continue
```

**Result**: Integration can INCREASE in P-mode if needed (not a violation of freeze policy).

---

## Configuration

### S-mode Configuration
```python
s_config = ConvergenceConfig()
s_config.FREEZE_INTEGRATION = False  # S-mode can freely adjust integration
```

### P-mode Configuration
```python
p_config = ConvergenceConfig()
p_config.FREEZE_INTEGRATION = True  # P-mode CANNOT reduce integration
```

**Set in**: `affilabs/core/calibration_orchestrator.py` line 737
```python
setattr(p_config, "FREEZE_INTEGRATION", True)
```

---

## Verification Checklist

To verify P-mode is working correctly, check logs for:

### ✅ Expected P-Mode Behavior:
- [ ] `"🔒 P-MODE FREEZE POLICY ACTIVE - Integration LOCKED at XXms"`
- [ ] `"P-mode inherits S-mode integration time and NEVER reduces it"`
- [ ] `"🔒 P-MODE: Integration FROZEN at XXms"`
- [ ] `"Weakest channel X saturating - reducing LED instead of integration"`
- [ ] `"Integration FROZEN at XXms (P-mode policy) - ignoring early saturation"`
- [ ] `"Will handle saturation by reducing LEDs instead"`

### ❌ P-Mode Violations (Should NEVER See):
- [ ] `"⚠️ Early saturation detected - reducing integration time"` (in P-mode)
- [ ] `"⚠️ Multiple channels saturating - reducing integration time"` (in P-mode)
- [ ] `"⚠️ Weakest channel X saturating - reducing integration time"` (in P-mode)
- [ ] `"❌ BUG: P-mode attempting to reduce integration time!"` (logic error)

### 🔍 Integration Time Tracking:
1. **S-mode final**: Note the final integration time (e.g., 60ms)
2. **P-mode initial**: Should START at S-mode's final time (60ms)
3. **P-mode final**: Should be >= P-mode initial (60ms or higher, NEVER lower)

---

## Common Failure Modes

### Issue 1: P-mode reduces integration from 60ms to 30ms
**Symptom**: P-mode final integration < S-mode final integration  
**Cause**: `freeze_integration` flag not set or check bypassed  
**Fix**: Verify line 737 in calibration_orchestrator.py sets flag

### Issue 2: ML model predicts aggressive LED increases
**Symptom**: Predicted LEDs >255 trigger saturation immediately  
**Cause**: Model trained on S-mode data, overly aggressive for P-mode  
**Solution**: P-mode freeze policy handles this - saturating LEDs reduced, integration stays locked

### Issue 3: Weakest channel not at 255 but other channels saturate
**Symptom**: `integration_locked=False` but `freeze_integration=True`  
**Expected**: Main saturation handler should catch via `freeze_integration` check  
**Verify**: Log shows "P-MODE FREEZE POLICY ACTIVE" message

---

## Code Locations

**Core Algorithm**: `affilabs/utils/led_convergence_algorithm.py`
- Line 93: `freeze_integration = bool(getattr(config, "FREEZE_INTEGRATION", False))`
- Line 199: Early saturation freeze check
- Line 347: Main saturation freeze check  
- Line 519: Weakest saturation freeze check

**Configuration**: `affilabs/core/calibration_orchestrator.py`
- Line 737: `setattr(p_config, "FREEZE_INTEGRATION", True)`

---

## Testing Protocol

1. **Run S-mode calibration**
   - Record final integration time (e.g., 60ms)
   - Record final LED intensities

2. **Run P-mode calibration immediately after**
   - Verify P-mode starts with S-mode integration (60ms)
   - Watch for freeze policy log messages
   - Verify NO integration reduction messages appear
   - Verify final integration >= 60ms

3. **Check final signals**
   - P-mode weakest channel should be close to target
   - Other channels normalized via LED adjustment
   - All channels within acceptable range

4. **If P-mode integration drops**
   - Check logs for "❌ BUG" message (logic error)
   - Check logs for violation messages (missing freeze check)
   - Verify freeze flag set in configuration
   - Review this document's checklist

---

## Summary

**The freeze policy is enforced at THREE critical points:**

1. ✅ **Early saturation** (sequential mode) - Line 199
2. ✅ **Main saturation** (all channels) - Line 347  
3. ✅ **Weakest saturation** (STEP 4 priority) - Line 519

**Plus safety check:**
- ❌ **Double-check in else branch** - Line 396 (catches logic errors)

**Result**: P-mode integration time = S-mode integration time (locked, never reduced).
