# S-Mode Calibration and P-Mode Saturation Fixes

**Status**: ✅ **FIXES APPLIED**
**Date**: October 12, 2025
**Files Modified**:
- `utils/spr_calibrator.py` (S-mode logic)
- `utils/spr_data_acquisition.py` (afterglow integration time)

---

## Issues Fixed

### Issue 1: S-Mode Calibration - All Channels Stuck at LED=128 ❌

**Problem**:
S-mode adaptive calibration was calling `calibrate_led_s_mode_adaptive()` for ALL channels, including the weakest channel. This caused:
- Weakest channel calibrated to ~128 (adaptive midpoint)
- Other channels also calibrated to similar values
- **WRONG LOGIC**: Weakest should be at 255, others scaled down

**Root Cause**:
```python
# OLD CODE (WRONG):
for ch in ch_list:
    calibrate_led_s_mode_adaptive(ch)  # Called for ALL channels

# Result: All channels end up around 128, not balanced
```

**Correct Logic**:
1. **Step 3.1**: Identify weakest channel by testing all at LED=168
2. **Step 3.2**: Optimize integration time with weakest at LED=**255** (max)
3. **Step 6**: Set weakest to **255**, calibrate ONLY other channels to match

**Fix Applied**:
```python
# utils/spr_calibrator.py - Line ~1468
# Store weakest channel
self.state.weakest_channel = weakest_ch
logger.info(f"   ➜ Weakest channel will be FIXED at LED=255")
logger.info(f"   ➜ Other channels will be adjusted DOWN to match")

# Line ~2668 - Skip weakest in LED calibration loop
weakest_ch = getattr(self.state, 'weakest_channel', None)
if weakest_ch:
    self.state.ref_intensity[weakest_ch] = MAX_LED_INTENSITY  # 255
    logger.info(f"✅ Weakest channel {weakest_ch} FIXED at LED={MAX_LED_INTENSITY}")

for ch in ch_list:
    if weakest_ch and ch == weakest_ch:
        logger.debug(f"   Skipping {ch} (weakest channel, already at 255)")
        continue  # ✅ SKIP WEAKEST

    calibrate_led_s_mode_adaptive(ch)  # Only calibrate OTHER channels
```

**Added to CalibrationState** (line ~245):
```python
self.weakest_channel: Optional[str] = None  # ✨ NEW: Track weakest channel
```

---

### Issue 2: P-Mode Live Data Still Saturating ❌

**Problem**:
P-mode raw data saturating despite `LIVE_MODE_INTEGRATION_FACTOR = 0.5` being applied in `spr_state_machine.py`.

**Investigation**:
The integration time scaling IS being applied correctly in `spr_state_machine.py` (line ~374):
```python
live_integration_seconds = integration_seconds * LIVE_MODE_INTEGRATION_FACTOR
self.app.usb.set_integration(live_integration_seconds)
logger.info(f"✅ Live mode integration scaled: {integration_seconds*1000:.1f}ms → {live_integration_seconds*1000:.1f}ms")
```

**Possible Causes**:
1. ✅ Integration time properly scaled (200ms → 100ms)
2. ❓ Afterglow correction using wrong integration time value
3. ❓ Integration time not being re-applied during live mode
4. ❓ Calibrated intensities too high for live mode

**Fix Applied** (Afterglow Integration Time):
```python
# utils/spr_data_acquisition.py - Line ~416
# OLD CODE (WRONG):
integration_time_ms = self.base_integration_time_factor * 1000.0  # This is just 1.0 or 0.5!

# NEW CODE (CORRECT):
integration_time_ms = 100.0  # Default fallback
if hasattr(self.usb, 'integration_time'):
    # Get ACTUAL integration time from spectrometer
    integration_time_ms = self.usb.integration_time * 1000.0
elif hasattr(self.usb, '_integration_time'):
    integration_time_ms = self.usb._integration_time * 1000.0

logger.debug(
    f"✨ Afterglow correction applied: prev_ch={self._last_active_channel}, "
    f"int_time={integration_time_ms:.1f}ms, correction={correction_value:.1f} counts"
)
```

---

## Code Changes Summary

### File: `utils/spr_calibrator.py`

#### Change 1: Store Weakest Channel (Line ~1468)
```python
# Find weakest channel
weakest_ch = min(channel_intensities, key=channel_intensities.get)

# ✨ CRITICAL FIX: Store weakest channel for LED calibration
self.state.weakest_channel = weakest_ch

logger.info(f"✅ Weakest channel identified: {weakest_ch}")
logger.info(f"   ➜ Weakest channel will be FIXED at LED=255")
logger.info(f"   ➜ Other channels will be adjusted DOWN to match")
```

#### Change 2: Fix LED Calibration Loop (Line ~2665)
```python
# Step 6: LED intensity calibration in S-mode (adaptive)
logger.debug("Step 6: LED intensity calibration (S-mode adaptive)")
self._emit_progress(6, "Calibrating LED intensities (adaptive S-mode)...")

# ✨ CRITICAL FIX: Set weakest channel to 255, calibrate others
weakest_ch = getattr(self.state, 'weakest_channel', None)
if weakest_ch:
    # Weakest channel FIXED at maximum LED intensity
    self.state.ref_intensity[weakest_ch] = MAX_LED_INTENSITY
    logger.info(f"✅ Weakest channel {weakest_ch} FIXED at LED={MAX_LED_INTENSITY}")
    logger.info(f"   Calibrating other channels to match...")

for ch in ch_list:
    if self._is_stopped():
        break

    # Skip weakest channel - already set to 255
    if weakest_ch and ch == weakest_ch:
        logger.debug(f"   Skipping {ch} (weakest channel, already at 255)")
        continue

    success = self.calibrate_led_s_mode_adaptive(ch)
    if not success:
        logger.warning(f"Failed to calibrate LED {ch} in S-mode (adaptive)")
```

#### Change 3: Add weakest_channel to CalibrationState (Line ~245)
```python
# LED intensities
self.ref_intensity: dict[str, int] = dict.fromkeys(CH_LIST, 0)
self.leds_calibrated: dict[str, int] = dict.fromkeys(CH_LIST, 0)
self.weakest_channel: Optional[str] = None  # ✨ NEW: Track weakest channel for S-mode calibration
```

### File: `utils/spr_data_acquisition.py`

#### Change 1: Fix Afterglow Integration Time (Line ~416)
```python
# ✨ NEW: Apply afterglow correction to dark noise if available
if (self.afterglow_correction and
    self._last_active_channel and
    self.afterglow_correction_enabled):
    try:
        # Get ACTUAL current integration time from spectrometer
        integration_time_ms = 100.0  # Default fallback
        if hasattr(self.usb, 'integration_time'):
            # USB4000 HAL adapter stores integration time in seconds
            integration_time_ms = self.usb.integration_time * 1000.0
        elif hasattr(self.usb, '_integration_time'):
            integration_time_ms = self.usb._integration_time * 1000.0

        # Calculate afterglow correction
        correction_value = self.afterglow_correction.calculate_correction(
            previous_channel=self._last_active_channel,
            integration_time_ms=integration_time_ms,
            delay_ms=self.led_delay * 1000
        )

        # Apply correction
        dark_correction = dark_correction - correction_value

        logger.debug(
            f"✨ Afterglow correction applied: prev_ch={self._last_active_channel}, "
            f"int_time={integration_time_ms:.1f}ms, correction={correction_value:.1f} counts"
        )
    except Exception as e:
        logger.warning(f"⚠️ Afterglow correction failed: {e}")
```

---

## Testing & Verification

### Test 1: S-Mode Calibration - Expected Logs

**During Step 3.1 (Weakest Channel Identification)**:
```
📊 Step 3.1: Identifying weakest channel...
✅ Weakest channel identified: c (12543.0 counts at LED=168 in 580-610nm)
   ➜ Weakest channel will be FIXED at LED=255
   ➜ Other channels will be adjusted DOWN to match
```

**During Step 6 (LED Calibration)**:
```
Step 6: LED intensity calibration (S-mode adaptive)
✅ Weakest channel c FIXED at LED=255
   Calibrating other channels to match...
   Skipping c (weakest channel, already at 255)
📊 Starting adaptive optimization for a from LED=128
Adaptive iter 0: LED=128, measured=45231.0 (69.0%), error=7231.0
Adaptive iter 1: LED=105, measured=38124.0 (58.2%), error=124.0
Channel a converged in 2 iterations: LED=105, intensity=38000.0 (58.0%)
```

**Expected Final Result**:
```
S-mode LED calibration complete: {'a': 105, 'b': 98, 'c': 255, 'd': 120}
```
✅ Channel `c` (weakest) at **255**
✅ Other channels **LOWER** (balanced to match)

### Test 2: P-Mode Saturation - Expected Logs

**On Live Mode Start**:
```
✅ Live mode integration scaled: 200.5ms → 100.3ms (factor=0.5)
✅ Applied scaled integration time to spectrometer
```

**During Live Acquisition** (debug mode):
```
✨ Afterglow correction applied: prev_ch=a, int_time=100.3ms, correction=8.2 counts
```
✅ Integration time should show **~100ms**, not 200ms

**In Spectroscopy View**:
- Raw P-mode intensity: **~30,000-40,000 counts** (60-65% of max)
- ❌ OLD: 55,000-60,000 counts (85-90% saturation)
- ✅ NEW: 30,000-40,000 counts (50-60% healthy)

---

## Additional Debugging (If Saturation Persists)

### Check Integration Time
```python
# Add temporary debug logging to spr_state_machine.py after line 390:
logger.info(f"🔍 DEBUG: USB integration time after set: {self.app.usb.integration_time * 1000:.1f}ms")
```

### Check Calibrated LED Intensities
If calibrated intensities are too high (e.g., all near 255), this could cause saturation even with scaled integration.

**Solution**: Re-run calibration with 200µm fiber mode disabled:
1. Edit `config/device_config.json`
2. Set `"optical_fiber_diameter_um": 400` (or comment out)
3. Re-run full calibration

### Check P-Mode vs S-Mode Intensities
P-mode should use S-mode calibrated intensities. If P-mode uses separate intensities, they might be too high.

---

## Root Cause Analysis

### S-Mode Issue: Why All Channels Were at 128

**Timeline**:
1. **Step 3.1**: Identify weakest channel (all tested at LED=168)
   - Result: Channel C weakest
2. **Step 3.2**: Optimize integration time with Channel C at LED=255
   - Result: Integration time = 200ms
3. **Step 6**: **BUG** - Called `calibrate_led_s_mode_adaptive()` for ALL channels
   - Channel A: Start at 128, converge to ~125
   - Channel B: Start at 128, converge to ~130
   - Channel C: Start at 128, converge to ~128 ❌ **WRONG**
   - Channel D: Start at 128, converge to ~135

**Expected** (with fix):
- Channel C: **FIXED at 255** (no calibration)
- Channels A, B, D: Calibrated to ~100-120 (balanced)

---

## Conclusion

✅ **S-Mode Fix**: Weakest channel now correctly fixed at 255, others scaled down
❓ **P-Mode Fix**: Afterglow correction improved, but saturation may need additional investigation

**Next Steps**:
1. Run full calibration and check S-mode LED values
2. Test live P-mode data for saturation
3. If saturation persists, add debug logging for integration time
4. Consider re-calibrating with fiber mode disabled if needed

---

**Document Status**: ✅ COMPLETE
**Last Updated**: October 12, 2025
**Author**: GitHub Copilot (diagnosis and fixes)
