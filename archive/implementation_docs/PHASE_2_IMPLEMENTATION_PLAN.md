# Phase 2 Implementation: Calibration Step 5 Dark Noise Correction

**Status**: 🚀 In Progress
**Date**: October 11, 2025
**Priority**: MEDIUM (Improves calibration quality, not as urgent as production Phase 1)

---

## Implementation Overview

### **Goal**: Apply afterglow correction to Step 5 dark noise measurement in calibration

**Problem**:
- **Step 1 dark noise** (line 2175): Clean measurement (32ms integration, no LEDs active yet) ✅
- **Step 5 dark noise** (line 2228): Contaminated measurement (55ms integration, LEDs active in Steps 2-4) ❌

**Solution**:
Apply afterglow correction to Step 5 dark noise using optical calibration data. Track which channels were active during Steps 2-4, then correct the dark noise measurement.

**Steps 2-4 LED Activity**:
- **Step 2** (Wavelength range): Activates Channel A briefly
- **Step 4** (Integration time): Activates ALL channels (a, b, c, d) sequentially
- **Step 5** (Dark noise): Measures with LEDs off, but phosphor afterglow present

**Last Active Channel**: Most likely Channel D (last in Step 4 sequence)

---

## Files to Modify

### **1. Modify: `utils/spr_calibrator.py`**
**Purpose**: Add optical calibration loading and apply correction to Step 5
**Status**: ⏳ To be implemented

**Key Changes**:

#### **A. Add optical calibration to `__init__()` (line ~476)**
```python
def __init__(
    self,
    ctrl: Union[PicoP4SPR, PicoEZSPR, None],
    usb: Union[USB4000, None],
    device_type: str,
    stop_flag: Any = None,
    calib_state: Optional["CalibrationState"] = None,
    optical_fiber_diameter: int = 100,
    led_pcb_model: str = "4LED",
    device_config: Optional[dict] = None,  # NEW: Add device_config parameter
):
    """Initialize the SPR calibrator."""
    # ... existing initialization ...

    # ✨ NEW: Load optical calibration for afterglow correction
    self.afterglow_correction = None
    self._last_active_channel = None  # Track last LED channel for correction
    self.afterglow_correction_enabled = False

    if device_config:
        optical_cal_file = device_config.get('optical_calibration_file')
        afterglow_enabled = device_config.get('afterglow_correction_enabled', True)

        if optical_cal_file and afterglow_enabled:
            try:
                from afterglow_correction import AfterglowCorrection
                self.afterglow_correction = AfterglowCorrection(optical_cal_file)
                self.afterglow_correction_enabled = True
                logger.info("✅ Optical calibration loaded for calibration")
                logger.info(f"   File: {Path(optical_cal_file).name}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to load optical calibration: {e}")
                logger.warning("⚠️ Afterglow correction DISABLED for calibration")
        else:
            logger.info("ℹ️ No optical calibration - afterglow correction disabled")
    else:
        logger.info("ℹ️ No device_config provided - afterglow correction disabled")
```

#### **B. Track last active channel in calibration methods**

**In `calibrate_wavelength_range()` (line ~947)**:
```python
def calibrate_wavelength_range(self) -> tuple[bool, float]:
    """Calibrate wavelength range using Channel A."""
    # ... existing code ...

    # Turn on Channel A for wavelength detection
    self.ctrl.turn_on_channel(ch="a")

    # ✨ NEW: Track that Channel A is active
    self._last_active_channel = "a"

    # ... rest of method ...
```

**In `calibrate_integration_time()` (line ~1119)**:
```python
def calibrate_integration_time(
    self, ch_list: list[str], integration_step: float = 0.005
) -> bool:
    """Calibrate integration time for each channel."""
    # ... existing code ...

    for ch in ch_list:
        # ... existing calibration code ...

        # Turn on channel
        self.ctrl.turn_on_channel(ch=ch)

        # ✨ NEW: Track active channel
        self._last_active_channel = ch

        # ... rest of loop ...

    # After loop completes, self._last_active_channel will be the LAST channel
    # For ch_list = ['a', 'b', 'c', 'd'], this will be 'd'
```

#### **C. Apply correction in `measure_dark_noise()` (line ~1559)**
```python
def measure_dark_noise(self) -> bool:
    """Measure dark noise with all LEDs off.

    Applies afterglow correction if:
    1. Optical calibration is loaded
    2. A previous channel was active (not first dark measurement in Step 1)
    3. Afterglow correction is enabled
    """
    try:
        # ... existing code: turn off LEDs, wait, measure ...

        dark_noise_sum = np.zeros(filtered_spectrum_length)

        for _scan in range(dark_scans):
            if self._is_stopped():
                return False

            raw_intensity = self.usb.read_intensity()
            if raw_intensity is None:
                logger.error("Failed to read intensity for dark noise")
                return False

            # Apply spectral filter to each dark noise measurement
            filtered_intensity = self._apply_spectral_filter(raw_intensity)
            dark_noise_sum += filtered_intensity

        # Average scans
        full_spectrum_dark_noise = dark_noise_sum / dark_scans

        # ✨ NEW: Apply afterglow correction
        if (self.afterglow_correction and
            self._last_active_channel and
            self.afterglow_correction_enabled):
            try:
                # Get current integration time
                integration_time_ms = self.state.integration * 1000.0

                # Calculate correction (uniform across spectrum)
                # Delay = settle_delay (500ms by default)
                correction_value = self.afterglow_correction.calculate_correction(
                    previous_channel=self._last_active_channel,
                    integration_time_ms=integration_time_ms,
                    delay_ms=settle_delay * 1000  # Convert to ms
                )

                # Apply correction (subtract afterglow)
                corrected_dark_noise = full_spectrum_dark_noise - correction_value

                logger.info(
                    f"✨ Afterglow correction applied to dark noise: "
                    f"Ch {self._last_active_channel.upper()} → "
                    f"{correction_value:.1f} counts removed"
                )
                logger.info(
                    f"   Dark noise: {np.mean(full_spectrum_dark_noise):.1f} → "
                    f"{np.mean(corrected_dark_noise):.1f} counts (avg)"
                )

                # Use corrected value
                full_spectrum_dark_noise = corrected_dark_noise

            except Exception as e:
                logger.warning(f"⚠️ Afterglow correction failed: {e}")
                logger.warning("⚠️ Using uncorrected dark noise")
                # Continue with uncorrected data
        else:
            if self._last_active_channel is None:
                logger.info("ℹ️ First dark measurement (Step 1) - no afterglow correction needed")
            elif not self.afterglow_correction:
                logger.info("ℹ️ No optical calibration - dark noise uncorrected")

        # Store dark noise (corrected if available)
        self.state.dark_noise = full_spectrum_dark_noise
        self.state.full_spectrum_dark_noise = full_spectrum_dark_noise

        # ... rest of existing code (save to disk, etc.) ...
```

---

## Expected Behavior

### **Step 1 Dark Noise** (Line 2175)
```
STEP 1: Dark Noise Measurement (FIRST - No LED contamination)
   Using temporary integration time: 32.0ms for initial dark
   ℹ️ First dark measurement (Step 1) - no afterglow correction needed
✅ Initial dark noise captured with ZERO LED contamination
```

**Reason**: No LEDs active yet, `self._last_active_channel = None`

---

### **Step 5 Dark Noise** (Line 2228)
```
STEP 5: Re-measuring Dark Noise (with optimized integration time)
   Using integration time: 55.0ms
   Last active channel: D (from Step 4)
✨ Afterglow correction applied to dark noise: Ch D → 1234.5 counts removed
   Dark noise: 950.2 → 850.7 counts (avg)
✅ Final dark noise captured with optimized integration time (corrected)
```

**Reason**: Channels active in Steps 2-4, correction applied

---

## Integration Time Considerations

| Step | Integration Time | Last Active Channel | Correction Applied? |
|------|------------------|---------------------|---------------------|
| Step 1 | 32ms (temporary) | None | ❌ No (clean) |
| Step 2 | 32ms | a | N/A (not dark) |
| Step 4 | Variable, final ~55ms | a, b, c, d (sequence) | N/A (not dark) |
| Step 5 | 55ms (optimized) | d (last from Step 4) | ✅ Yes (contaminated) |

**Delay for Correction**:
- `settle_delay = max(LED_DELAY, 0.5)` (typically 500ms)
- This is the time between LEDs turning off and dark measurement
- Passed to `calculate_correction(delay_ms=500)`

---

## Modification Locations

### **File: `utils/spr_calibrator.py`**

1. **Line ~476** (`__init__` method):
   - Add `device_config` parameter
   - Load `AfterglowCorrection`
   - Initialize `self._last_active_channel = None`

2. **Line ~947** (`calibrate_wavelength_range` method):
   - Add `self._last_active_channel = "a"` after turning on Channel A

3. **Line ~1119** (`calibrate_integration_time` method):
   - Add `self._last_active_channel = ch` inside channel loop

4. **Line ~1559** (`measure_dark_noise` method):
   - Apply afterglow correction after averaging scans
   - Log correction status

---

## Caller Updates

### **File: `main.py` (or wherever SPRCalibrator is instantiated)**

**Before**:
```python
calibrator = SPRCalibrator(
    ctrl=ctrl,
    usb=usb,
    device_type=device_type,
    stop_flag=stop_flag,
    calib_state=state,
    optical_fiber_diameter=fiber_diameter,
    led_pcb_model=led_pcb_model,
)
```

**After**:
```python
calibrator = SPRCalibrator(
    ctrl=ctrl,
    usb=usb,
    device_type=device_type,
    stop_flag=stop_flag,
    calib_state=state,
    optical_fiber_diameter=fiber_diameter,
    led_pcb_model=led_pcb_model,
    device_config=device_config,  # NEW: Pass device config
)
```

---

## Testing Plan

### **Test 1: Verify Step 1 is Uncorrected**
```
Expected Log:
STEP 1: Dark Noise Measurement (FIRST - No LED contamination)
ℹ️ First dark measurement (Step 1) - no afterglow correction needed
✅ Initial dark noise captured with ZERO LED contamination
```

### **Test 2: Verify Step 5 is Corrected**
```
Expected Log:
STEP 5: Re-measuring Dark Noise (with optimized integration time)
✨ Afterglow correction applied to dark noise: Ch D → 1234.5 counts removed
   Dark noise: 950.2 → 850.7 counts (avg)
✅ Final dark noise captured with optimized integration time (corrected)
```

### **Test 3: Compare With/Without Correction**
1. Run calibration **without** optical calibration file
   - Should log: `ℹ️ No optical calibration - dark noise uncorrected`
2. Run calibration **with** optical calibration file
   - Should log: `✨ Afterglow correction applied...`
3. Compare Step 5 dark noise values - corrected should be lower

---

## Success Criteria

✅ **Step 1**: No correction applied (first measurement, clean)
✅ **Step 5**: Correction applied (LEDs active in Steps 2-4)
✅ **Graceful Degradation**: Works without optical calibration (just logs info)
✅ **Logging**: Clear status messages for debugging
✅ **No Crashes**: Robust error handling

---

## Timeline

**Estimated Implementation Time**: 1-2 hours

1. **Modify `__init__()`**: 15 minutes
2. **Track active channels**: 15 minutes
3. **Apply correction in `measure_dark_noise()`**: 30 minutes
4. **Update callers**: 15 minutes
5. **Testing**: 30 minutes

---

**Status**: Ready to implement
**Next Action**: Modify `SPRCalibrator.__init__()` to accept `device_config` and load optical calibration
**Last Updated**: October 11, 2025
