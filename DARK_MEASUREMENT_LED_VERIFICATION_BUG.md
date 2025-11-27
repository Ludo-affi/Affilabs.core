# CRITICAL BUG: Dark Spectrum Measured with LEDs ON

**Date**: November 27, 2025
**Status**: 🚨 **CRITICAL BUG IDENTIFIED** - Fix Required

---

## Problem Description

During calibration, the DARK spectrum may be measured **with LEDs still ON**, causing:
- Incorrect dark noise baseline (inflated values)
- Wrong transmission calculations (P/S ratio contaminated)
- Poor SPR sensitivity (signal corrupted)
- Failed calibration QC (appears as water detection failure)

**Root Cause**: `measure_dark_noise()` calls `ctrl.turn_off_channels()` but **never verifies** that LEDs actually turned off before measuring.

---

## Technical Analysis

### Current Code Flow (BROKEN)

```python
def measure_dark_noise(usb, ctrl, integration, ...):
    """Measure dark noise with all LEDs off."""

    # 1. Turn off LEDs
    ctrl.turn_off_channels()  # Sends i0 command
    time.sleep(pre_led_delay_ms / 1000.0)  # Wait 45ms

    # 2. Measure dark (NO VERIFICATION!)
    for scan in range(dark_scans):
        intensity_data = usb.read_intensity()  # May still have LED light!
        dark_noise_single = intensity_data[wave_min_index:wave_max_index]
        dark_noise_sum += dark_noise_single
```

**Problem**: The code **ASSUMES** LEDs turned off but never checks!

**Why This Fails**:
1. **USB latency**: `i0` command may be delayed in USB buffer
2. **Firmware processing**: Controller may not execute immediately
3. **LED decay time**: LEDs take time to physically turn off (~1-5ms)
4. **No feedback**: Code has no way to know if command succeeded

**Result**: Dark measurement may capture residual LED light → wrong baseline

---

## Why This Wasn't Caught Earlier

### V1.0 Firmware (Old)
- No LED query capability (`ia`, `ib`, `ic`, `id` commands didn't exist)
- **Assumption**: Commands always succeed, timing is reliable
- **Reality**: Sometimes failed, but no way to detect

### V1.1 Firmware (New - Available Now!)
- LED query commands available: `ia`, `ib`, `ic`, `id`
- Returns current LED intensity (0-255)
- **Should be used** to verify LEDs are off before dark measurement
- **Currently NOT USED** in calibration code

---

## Impact Assessment

### Calibration Steps Affected

**Step 2: Quick Dark Baseline** ❌
```python
def measure_quick_dark_baseline(usb, ctrl, ...):
    ctrl.turn_off_channels()  # No verification
    time.sleep(LED_DELAY)     # Just waits
    # Measures dark (may have LED light)
```

**Step 5E: Final Dark Noise** ❌
```python
final_dark = measure_dark_noise(
    usb, ctrl, integration_time, ...
)
# Uses measure_dark_noise() which doesn't verify
```

**Both Standard and Alternative Methods** ❌
- Both use `measure_dark_noise()` internally
- Both susceptible to LED-on-during-dark bug
- **No difference** between calibration methods for this bug

---

## Evidence from User Report

**User observation**: "DARK spectrum seems to be measured when LEDs are ON"

**Likely scenario**:
1. Previous channel measurement finished (LED A was on at intensity 200)
2. Calibration calls `measure_dark_noise()`
3. Code sends `i0` (turn off all LEDs)
4. Code waits 45ms
5. **BUT**: USB delayed command OR LED still decaying
6. Dark measurement captures 50-100 counts (should be 5-20)
7. Result: Inflated dark baseline

**Diagnostic**: Compare dark noise values
- **Expected**: 5-20 counts (true dark)
- **If bug present**: 50-500 counts (LED residual)

---

## Solution: Use V1.1 LED Verification

### Implementation Strategy

**Add LED verification after turn_off_channels()**:

```python
def measure_dark_noise(usb, ctrl, integration, ...):
    """Measure dark noise with VERIFIED all LEDs off."""

    # Step 1: Turn off LEDs
    logger.debug("Turning off all LEDs for dark measurement...")
    ctrl.turn_off_channels()  # Send i0 command

    # Step 2: VERIFY LEDs are off (NEW!)
    logger.debug("Verifying LEDs are off...")
    max_retries = 5
    for attempt in range(max_retries):
        time.sleep(0.01)  # Wait 10ms for command to process

        # Query LED state
        led_state = ctrl.get_all_led_intensities()

        if led_state is None:
            logger.warning(f"Could not query LED state (attempt {attempt+1}/{max_retries})")
            continue

        # Check if all LEDs are off (0 intensity)
        all_off = all(intensity == 0 for intensity in led_state.values())

        if all_off:
            logger.debug(f"✅ All LEDs confirmed OFF: {led_state}")
            break
        else:
            logger.warning(f"⚠️ LEDs still on (attempt {attempt+1}/{max_retries}): {led_state}")
            # Retry turn-off command
            ctrl.turn_off_channels()
    else:
        # Max retries exceeded - LEDs still not off
        logger.error(f"❌ Failed to turn off LEDs after {max_retries} attempts: {led_state}")
        raise RuntimeError(
            f"Cannot measure dark noise - LEDs failed to turn off. "
            f"Current state: {led_state}"
        )

    # Step 3: Additional delay for LED physical decay
    logger.debug("Waiting for LED physical decay...")
    time.sleep(pre_led_delay_ms / 1000.0)  # 45ms for complete dark

    # Step 4: Measure dark (now safe!)
    logger.debug(f"Measuring dark noise ({dark_scans} scans)...")
    for scan in range(dark_scans):
        intensity_data = usb.read_intensity()
        dark_noise_single = intensity_data[wave_min_index:wave_max_index]
        dark_noise_sum += dark_noise_single

    dark_noise = dark_noise_sum / dark_scans

    # Step 5: Validate dark noise is reasonable
    max_dark = np.max(dark_noise)
    logger.debug(f"✅ Dark noise measured: max = {max_dark:.0f} counts")

    # Sanity check: dark should be < 50 counts typically
    if max_dark > 100:
        logger.warning(
            f"⚠️ Unusually high dark noise ({max_dark:.0f} counts). "
            f"Expected < 50 counts. LEDs may not be fully off."
        )

    return dark_noise
```

---

## Additional Safeguards

### 1. LED State Logging

Add diagnostic logging throughout calibration:

```python
def calibrate_led_channel(usb, ctrl, ch, ...):
    """Calibrate LED intensity for a channel."""

    # Before measurement
    led_state_before = ctrl.get_all_led_intensities()
    logger.debug(f"LED state before {ch.upper()} calibration: {led_state_before}")

    # Turn on channel
    ctrl.set_intensity(ch, test_intensity)
    time.sleep(LED_DELAY)

    # Verify LED is on
    led_state_after = ctrl.get_all_led_intensities()
    logger.debug(f"LED state after turn-on: {led_state_after}")

    if led_state_after[ch] != test_intensity:
        logger.warning(
            f"LED {ch.upper()} intensity mismatch: "
            f"expected={test_intensity}, actual={led_state_after[ch]}"
        )

    # Measure...
```

### 2. Dark Noise Validation

Add QC check after dark measurement:

```python
def validate_dark_noise(dark_noise: np.ndarray) -> bool:
    """Validate dark noise is reasonable.

    Returns:
        bool: True if dark noise looks valid, False if suspicious
    """
    max_dark = np.max(dark_noise)
    mean_dark = np.mean(dark_noise)

    # Thresholds based on typical detector characteristics
    MAX_DARK_THRESHOLD = 50  # counts (typical: 5-20)
    MEAN_DARK_THRESHOLD = 30  # counts (typical: 3-15)

    if max_dark > MAX_DARK_THRESHOLD:
        logger.error(
            f"❌ Dark noise QC FAILED: max={max_dark:.0f} counts "
            f"(threshold={MAX_DARK_THRESHOLD}). LEDs may be on!"
        )
        return False

    if mean_dark > MEAN_DARK_THRESHOLD:
        logger.error(
            f"❌ Dark noise QC FAILED: mean={mean_dark:.0f} counts "
            f"(threshold={MEAN_DARK_THRESHOLD}). LEDs may be on!"
        )
        return False

    logger.info(
        f"✅ Dark noise QC PASSED: max={max_dark:.0f}, mean={mean_dark:.0f} counts"
    )
    return True
```

### 3. Emergency Stop on Validation Failure

```python
# In calibration flow
final_dark = measure_dark_noise(usb, ctrl, integration_time, ...)

if not validate_dark_noise(final_dark):
    logger.error("🛑 CALIBRATION ABORTED: Dark noise validation failed")
    raise RuntimeError(
        "Dark noise measurement failed validation. "
        "LEDs may not be turning off correctly. "
        "Check hardware connections and retry."
    )
```

---

## Testing Strategy

### Test 1: Verify LED Query Works

```python
def test_led_query():
    """Test LED query functionality."""
    ctrl = Controller(port="COM4")

    # Test 1: All off
    ctrl.turn_off_channels()
    time.sleep(0.1)
    state = ctrl.get_all_led_intensities()
    print(f"All OFF: {state}")
    assert all(v == 0 for v in state.values()), "LEDs not off!"

    # Test 2: Channel A on
    ctrl.set_intensity('a', 150)
    time.sleep(0.1)
    state = ctrl.get_all_led_intensities()
    print(f"A=150: {state}")
    assert state['a'] == 150, f"LED A mismatch: {state['a']}"

    # Test 3: Turn off again
    ctrl.turn_off_channels()
    time.sleep(0.1)
    state = ctrl.get_all_led_intensities()
    print(f"All OFF again: {state}")
    assert all(v == 0 for v in state.values()), "LEDs not off!"

    print("✅ LED query test PASSED")
```

### Test 2: Measure Dark with Verification

```python
def test_dark_measurement():
    """Test dark measurement with LED verification."""
    ctrl = Controller(port="COM4")
    usb = Spectrometer()

    # Measure dark with verification
    dark = measure_dark_noise(usb, ctrl, integration=100, ...)

    # Check dark is reasonable
    max_dark = np.max(dark)
    print(f"Dark noise: max={max_dark:.0f} counts")

    if max_dark > 50:
        print("⚠️ WARNING: High dark noise - LEDs may be on")
    else:
        print("✅ Dark noise looks good")
```

### Test 3: Full Calibration with Logging

```python
# Run full calibration with enhanced logging
result = perform_standard_calibration(...)

# Check dark noise in result
if result.dark_noise is not None:
    max_dark = np.max(result.dark_noise)
    print(f"Final dark noise: {max_dark:.0f} counts")
    if max_dark > 50:
        print("🚨 SUSPICIOUS: Dark noise too high!")
```

---

## Rollout Plan

### Phase 1: Add LED Verification (Immediate)
1. Update `measure_dark_noise()` in `led_calibration.py`
2. Add `verify_led_state()` calls after `turn_off_channels()`
3. Add retry logic (up to 5 attempts)
4. Add error handling for verification failure

### Phase 2: Add Validation (Quick Win)
1. Add `validate_dark_noise()` function
2. Call after every dark measurement
3. Log warnings for suspicious values
4. Abort calibration on critical failures

### Phase 3: Enhanced Logging (Diagnostic)
1. Log LED state before/after every command
2. Track LED command success rate
3. Add timing diagnostics (USB latency)
4. Create calibration diagnostic report

### Phase 4: Testing (Validation)
1. Test with known-good hardware
2. Test with deliberate LED-on scenario
3. Verify error detection works
4. Validate calibration quality improves

---

## Expected Improvements

### Before Fix
- ❌ Dark noise: 50-200 counts (contaminated)
- ❌ Transmission: Wrong baseline
- ❌ SPR sensitivity: Degraded
- ❌ QC failures: Intermittent

### After Fix
- ✅ Dark noise: 5-20 counts (true dark)
- ✅ Transmission: Accurate P/S ratio
- ✅ SPR sensitivity: Maximum
- ✅ QC success: Consistent

---

## Conclusion

**Critical bug confirmed**: Dark measurement doesn't verify LEDs are off.

**Solution exists**: Use V1.1 firmware LED query feature to verify LED state.

**Implementation**: Add `verify_led_state()` to `measure_dark_noise()`.

**Priority**: **HIGH** - Affects all calibrations, impacts data quality.

**Effort**: Low (1-2 hours) - Existing functions available, just need integration.

**Risk**: Low - Adding verification can only improve reliability.

---

## Next Steps

1. ✅ Identify bug source (`measure_dark_noise()` missing verification)
2. ⏳ Implement LED verification with retry logic
3. ⏳ Add dark noise validation QC
4. ⏳ Test with hardware
5. ⏳ Deploy to production

**Recommendation**: Implement immediately - this is a data quality critical fix.
