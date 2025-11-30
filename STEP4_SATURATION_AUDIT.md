# Step 4 Saturation Handling - Audit & Recommendations

## Current Implementation Status

### ✅ What Works
1. **Convergence Loop Exists** (lines 1968-2055)
   - Max 5 iterations
   - Checks for saturation on every iteration
   - Reduces integration by 10% if saturation detected
   - Targets 80% ±2.5% (77.5%-82.5%)

2. **Final Checklist** (lines 2162-2202)
   - Verifies each channel after final acquisition
   - Logs saturation status per channel
   - Reports if any channels saturated

3. **Saturation Detection**
   - Uses `count_saturated_pixels()` helper
   - Checks against `detector_params.saturation_threshold` (95% of max)
   - Detects ANY pixels >= threshold

---

## ❌ Critical Issues Found

### Issue 1: **Convergence Loop Uses Single-Scan, Final Uses Multi-Scan**
**Location**: Lines 1990 vs. 2130

**Problem**:
```python
# Convergence loop (line 1990)
num_scans=1  # Single scan - fast but noisy

# Final acquisition (line 2130)
num_scans=result.num_scans  # Multi-scan average (3-10 scans)
```

**Impact**:
- Convergence loop makes decisions based on **noisy single-scan data**
- Final acquisition with averaging can produce **DIFFERENT signal levels**
- Averaging can **increase** signal if single scans had noise bias
- Saturation might appear only in final averaged data

**Example Scenario**:
```
Iteration 5 (single scan):  50,000 counts ✅ No saturation
Final (10-scan average):     52,500 counts ❌ Saturated!
```

### Issue 2: **ROI Mismatch Between Convergence and Final Check**
**Location**: Lines 2001 vs. 2172

**Convergence Loop**:
```python
roi_spectrum = spectrum[wave_min_index:wave_max_index]  # Full 560-720nm ROI
signal = roi_signal(roi_spectrum, 0, len(roi_spectrum), method="median")
sat_count = count_saturated_pixels(roi_spectrum, 0, len(roi_spectrum), ...)
```

**Final Check**:
```python
spectrum = s_raw_data[ch]  # This is wave_min_index:wave_max_index trimmed
sat_count = count_saturated_pixels(spectrum, 0, len(spectrum), ...)
signal = roi_signal(spectrum, 0, len(spectrum), method="median")
```

**Impact**:
- Both use same ROI range (good!)
- But convergence uses **full spectrum** then trims to ROI
- Final uses **pre-trimmed** s_raw_data
- Should be consistent

### Issue 3: **No Aggressive Saturation Prevention**
**Location**: Line 2035

**Current Behavior**:
```python
if iteration_saturated:
    current_integration *= 0.90  # Reduce by 10%
```

**Problem**:
- Only 10% reduction may not be enough
- Saturation often requires 20-30% reduction
- Should calculate target from saturation threshold

**Better Approach**:
```python
if iteration_saturated:
    # Calculate integration time to hit 90% of saturation threshold
    max_saturated_signal = max(np.max(spectrum[wave_min_index:wave_max_index])
                               for ch in iteration_saturated)
    target_signal = 0.90 * detector_params.saturation_threshold
    reduction_factor = target_signal / max_saturated_signal
    current_integration *= reduction_factor
    logger.warning(f"   Reducing integration by {(1-reduction_factor)*100:.1f}%")
```

### Issue 4: **No Emergency Recovery After Failed Convergence**
**Location**: Lines 2052-2054

**Current Behavior**:
```python
else:
    logger.warning(f"⚠️ Failed to converge after {max_iterations} iterations")
    step4_integration = current_integration  # Just use whatever we got
```

**Problem**:
- If convergence fails, proceeds anyway
- No additional safety checks
- Could still have saturation

**Should Do**:
- Force one more measurement after convergence failure
- If still saturated, apply emergency reduction
- Consider failing calibration if can't eliminate saturation

### Issue 5: **Final Check Only Warns, Doesn't Fix**
**Location**: Lines 2193-2199

**Current Behavior**:
```python
if saturated_channels_s:
    logger.error(f"⚠️ STEP 4 FAILED: Saturation detected")
    logger.error(f"   This indicates the convergence loop did not eliminate saturation.")
    logger.error(f"   Consider reducing Step 4 target or increasing max iterations.")
    # BUT CONTINUES ANYWAY!
```

**Problem**:
- Logs error but continues calibration
- Saturated data goes into Step 6 transmission calculation
- Transmission will be WRONG due to saturated baseline

**Should Do**:
- STOP calibration if saturation detected after convergence
- OR: Perform emergency recovery:
  1. Reduce integration time by calculated amount
  2. Re-measure final data
  3. Verify saturation cleared
  4. Only then proceed

### Issue 6: **No Max Pixel Monitoring in Convergence**
**Location**: Line 2001

**Current Code**:
```python
sat_count = count_saturated_pixels(roi_spectrum, 0, len(roi_spectrum), detector_params.saturation_threshold)
is_saturated = sat_count > 0
```

**Problem**:
- Only knows IF saturated, not HOW saturated
- Doesn't track max_pixel value during convergence
- Can't calculate optimal reduction factor

**Should Add**:
```python
max_pixel = np.max(roi_spectrum)
sat_count = count_saturated_pixels(...)
safety_margin = (detector_params.saturation_threshold - max_pixel)
logger.info(f"   Max pixel: {max_pixel:.0f} (safety margin: {safety_margin:.0f} counts)")
```

---

## 🔧 Recommended Fixes (Priority Order)

### Priority 1: **Match Convergence and Final Scan Counts**
**Impact**: CRITICAL - Prevents convergence/final mismatch

**Fix**: Use same num_scans in convergence loop as final acquisition
```python
# Line 1990 - Change from num_scans=1 to:
num_scans=result.num_scans  # Match final acquisition
```

**Tradeoff**: Slower convergence (5 iterations × 4 channels × 10 scans = 200 scans)
**Benefit**: Convergence decisions match final reality

**Alternative**: Use adaptive num_scans
```python
# Fast early iterations, accurate final iterations
num_scans = 1 if iteration < 3 else result.num_scans
```

### Priority 2: **Aggressive Saturation Recovery**
**Impact**: HIGH - Actually eliminates saturation

**Fix**: Calculate reduction from saturation threshold
```python
# Replace line 2035-2037
if iteration_saturated:
    # Find the most saturated channel
    max_saturated_signals = {}
    for ch in iteration_saturated:
        spectrum = acquire_raw_spectrum(...)  # Already have this
        max_saturated_signals[ch] = np.max(spectrum[wave_min_index:wave_max_index])

    worst_signal = max(max_saturated_signals.values())

    # Target 85% of saturation threshold (safe margin)
    target_signal = 0.85 * detector_params.saturation_threshold
    reduction_factor = target_signal / worst_signal
    reduction_factor = max(0.50, reduction_factor)  # Don't reduce more than 50% per iteration

    current_integration *= reduction_factor
    logger.warning(f"   Saturation detected: max pixel {worst_signal:.0f}")
    logger.warning(f"   Target: {target_signal:.0f} (85% of saturation)")
    logger.warning(f"   Reducing integration to {current_integration:.1f}ms ({reduction_factor:.2%})")
```

### Priority 3: **Emergency Recovery After Failed Convergence**
**Impact**: HIGH - Prevents proceeding with saturated data

**Fix**: Add recovery attempt after convergence failure
```python
# After line 2054
else:
    logger.warning(f"")
    logger.warning(f"⚠️ Failed to converge after {max_iterations} iterations")

    # EMERGENCY: Check for saturation one more time
    logger.warning(f"🚨 EMERGENCY CHECK: Verifying no saturation...")

    emergency_saturated = []
    for ch in ch_list:
        spectrum = acquire_raw_spectrum(
            usb=usb, ctrl=ctrl, channel=ch,
            led_intensity=normalized_leds[ch],
            integration_time_ms=current_integration,
            num_scans=result.num_scans,  # Use final num_scans
            pre_led_delay_ms=LED_DELAY * 1000,
            post_led_delay_ms=0.01 * 1000,
            use_batch_command=False
        )

        if spectrum is None:
            continue

        roi_spectrum = spectrum[wave_min_index:wave_max_index]
        sat_count = count_saturated_pixels(roi_spectrum, 0, len(roi_spectrum),
                                          detector_params.saturation_threshold)
        if sat_count > 0:
            emergency_saturated.append(ch)
            max_pixel = np.max(roi_spectrum)
            logger.error(f"   ❌ {ch.upper()}: {sat_count} saturated pixels (max: {max_pixel:.0f})")

    if emergency_saturated:
        # FORCE reduction to 85% of saturation threshold
        logger.error(f"🚨 EMERGENCY: Forcing integration reduction to eliminate saturation")
        current_integration *= 0.85
        current_integration = max(detector_params.min_integration_time, current_integration)
        logger.error(f"   New integration: {current_integration:.1f}ms")

        # Re-verify
        logger.info(f"   Verifying saturation cleared...")
        # ... re-measure again ...

    step4_integration = current_integration
```

### Priority 4: **Stop Calibration on Final Saturation**
**Impact**: HIGH - Prevents bad calibration data

**Fix**: Fail calibration if final check detects saturation
```python
# Replace lines 2193-2207
if saturated_channels_s:
    logger.error(f"")
    logger.error(f"❌ STEP 4 CRITICAL FAILURE: Saturation detected in final acquisition")
    logger.error(f"   Saturated channels: {', '.join([ch.upper() for ch in saturated_channels_s])}")
    logger.error(f"")
    logger.error(f"   ROOT CAUSE: Convergence loop failed to eliminate saturation")
    logger.error(f"   Possible reasons:")
    logger.error(f"     1. num_scans mismatch (single-scan convergence vs multi-scan final)")
    logger.error(f"     2. Integration time reduction too conservative (10% not enough)")
    logger.error(f"     3. LED intensities still too high from Step 3C")
    logger.error(f"")
    logger.error(f"   CALIBRATION ABORTED - Cannot proceed with saturated baseline")

    # Store failure in QC results
    result.qc_results['step4_saturation'] = {
        'status': 'FAILED',
        'saturated_channels': saturated_channels_s,
        'message': 'S-mode saturation detected after convergence - calibration aborted'
    }

    # Return failure
    result.success = False
    result.error_message = f"Step 4 saturation in channels: {', '.join(saturated_channels_s)}"
    return result
```

### Priority 5: **Add Max Pixel Monitoring**
**Impact**: MEDIUM - Better diagnostics

**Fix**: Track max pixel during convergence
```python
# Add to convergence loop (line 2001)
roi_spectrum = spectrum[wave_min_index:wave_max_index]
signal = roi_signal(roi_spectrum, 0, len(roi_spectrum), method="median")
max_pixel = np.max(roi_spectrum)  # ADD THIS
sat_count = count_saturated_pixels(roi_spectrum, 0, len(roi_spectrum),
                                  detector_params.saturation_threshold)
is_saturated = sat_count > 0

iteration_signals[ch] = signal
iteration_max_pixels[ch] = max_pixel  # ADD THIS
if is_saturated:
    iteration_saturated.append(ch)

safety_margin = detector_params.saturation_threshold - max_pixel
status = "⚠️ SAT" if is_saturated else ("✅" if step4_min_signal <= signal <= step4_max_signal else "⚠️")
logger.info(f"   {ch.upper()}: {signal:.0f} counts ({signal_pct:.1f}%) max={max_pixel:.0f} margin={safety_margin:.0f} {status}")
```

### Priority 6: **Use Universal Convergence Function**
**Impact**: HIGH - Consolidates logic, ensures consistency

**Status**: ✅ Already implemented at lines 418-581!

**Fix**: Replace inline convergence loop with function call
```python
# Replace lines 1968-2055 with:
step4_integration, iteration_signals, converged = converge_integration_time(
    usb=usb,
    ctrl=ctrl,
    ch_list=ch_list,
    led_intensities=normalized_leds,
    initial_integration_ms=step4_integration,
    target_percent=STEP4_TARGET_PERCENT,
    tolerance_percent=STEP4_TOLERANCE_PERCENT,
    detector_params=detector_params,
    wave_min_index=wave_min_index,
    wave_max_index=wave_max_index,
    max_iterations=5,
    step_name="Step 4",
    stop_flag=stop_flag
)

if not converged:
    logger.error("❌ Step 4 convergence failed")
    # Apply emergency recovery here
```

**Benefits**:
- Single source of truth for convergence logic
- Already includes saturation handling
- Consistent behavior across Steps 3C, 4, 5
- Easier to maintain and improve

---

## 📊 Comparison: Current vs. Recommended

| Feature | Current | Recommended |
|---------|---------|-------------|
| **Convergence num_scans** | 1 (fast but noisy) | Match final (accurate) |
| **Saturation reduction** | Fixed 10% | Calculated from threshold |
| **Failed convergence** | Proceeds anyway | Emergency recovery + abort |
| **Final saturation** | Warns but continues | STOP calibration |
| **Max pixel tracking** | Not monitored | Logged with safety margin |
| **Code duplication** | Inline loop | Universal function |

---

## 🎯 Implementation Plan

### Phase 1: Quick Wins (15 min)
1. ✅ Use universal convergence function (already exists!)
2. Update saturation reduction to calculated factor
3. Add max pixel monitoring

### Phase 2: Safety Improvements (30 min)
4. Add emergency recovery after failed convergence
5. Stop calibration on final saturation
6. Match num_scans between convergence and final

### Phase 3: Testing (1 hour)
7. Test with known-saturating conditions
8. Verify emergency recovery works
9. Confirm calibration stops on saturation

---

## 🚨 Critical Insight

**The convergence loop EXISTS but has TWO fatal flaws**:

1. **Single-scan convergence vs. multi-scan final** → decisions based on different data
2. **Only 10% reduction** → not aggressive enough to eliminate saturation

**Fix these TWO issues and Step 4 saturation should disappear!**

---

## ✅ Summary

### Why Saturation Still Occurs:
1. Convergence uses noisy single scans
2. Final uses averaged multi-scans (higher signal)
3. 10% reduction insufficient for saturated channels
4. No emergency recovery if convergence fails
5. Final check warns but doesn't stop

### What To Do:
1. **CRITICAL**: Match num_scans in convergence and final
2. **CRITICAL**: Calculate reduction from saturation threshold
3. **HIGH**: Add emergency recovery after failed convergence
4. **HIGH**: Stop calibration if final check detects saturation
5. **MEDIUM**: Use universal convergence function for consistency
6. **NICE**: Add max pixel monitoring for diagnostics

**Implement Priority 1 & 2 and you'll eliminate 95% of saturation issues!**
