# P-Mode Saturation Debug Analysis

**Status**: 🔍 **INVESTIGATION IN PROGRESS**
**Date**: October 12, 2025
**Issue**: P-mode live data still saturating despite `LIVE_MODE_INTEGRATION_FACTOR = 0.5`

---

## Investigation Timeline

### Observation
P-mode raw intensity data saturating during live measurements even after implementing:
1. `LIVE_MODE_INTEGRATION_FACTOR = 0.5` in settings.py
2. Integration time scaling in `spr_state_machine.py:sync_from_shared_state()`

### Expected Behavior
- **Calibration**: 200.5ms integration time (optimized for 80% detector max)
- **Live Mode**: 100.3ms integration time (50% scaling to prevent saturation)
- **Result**: Raw P-mode intensity ~40% of max (~26,000 counts)

### Actual Behavior
- **Live Mode**: Still saturating (~55,000-60,000 counts)
- **Conclusion**: Integration time scaling NOT being applied

---

## Root Cause Analysis

### Code Flow Investigation

**1. Integration Time Scaling Location** (`spr_state_machine.py:370-394`):
```python
# Calculate dynamic scan count based on integration time
# Apply live mode integration time scaling to prevent saturation
if self.calib_state.integration > 0:
    from settings import LIVE_MODE_INTEGRATION_FACTOR
    integration_seconds = self.calib_state.integration

    # Scale integration time for live mode to prevent saturation
    live_integration_seconds = integration_seconds * LIVE_MODE_INTEGRATION_FACTOR

    logger.info(
        f"✅ Live mode integration scaled: {integration_seconds*1000:.1f}ms → {live_integration_seconds*1000:.1f}ms (factor={LIVE_MODE_INTEGRATION_FACTOR})"
    )

    # Apply the scaled integration time to the spectrometer
    if hasattr(self.app, 'usb') and self.app.usb is not None:
        if hasattr(self.app.usb, 'set_integration'):
            self.app.usb.set_integration(live_integration_seconds)
            logger.info(f"✅ Applied scaled integration time to spectrometer")
        elif hasattr(self.app.usb, 'set_integration_time'):
            self.app.usb.set_integration_time(live_integration_seconds)
            logger.info(f"✅ Applied scaled integration time to spectrometer")
```

**2. When is this called?** (`spr_state_machine.py:222`):
```python
# 🎯 Sync from shared calibration state before creating acquisition
if self.calib_state is not None:
    self.sync_from_shared_state()  # ← CALLED HERE
```

**3. Who calls this?** (`spr_state_machine.py:817-820`):
```python
def _handle_calibrated(self) -> None:
    """Start data acquisition."""
    if not self.data_acquisition:
        logger.debug("Creating data acquisition wrapper...")
        try:
            # Create the wrapper that handles all the complex data setup
            # 🎯 Pass shared calibration state - no data copying needed!
            self.data_acquisition = DataAcquisitionWrapper(self.app, calib_state=self.calib_state)
            # ↑ This __init__() calls sync_from_shared_state() on line 222
```

---

## Problem Hypothesis

### Missing Log Messages

**Expected logs after calibration completes**:
```
✅ Live mode integration scaled: 200.5ms → 100.3ms (factor=0.5)
✅ Applied scaled integration time to spectrometer
```

**Actual logs**: **THESE MESSAGES ARE MISSING!**

### Possible Causes

1. **Condition fails**: `if self.calib_state.integration > 0:` is FALSE
   - Calibration integration time is 0 or not set?
   - Unlikely - calibration succeeded

2. **USB object check fails**: `if hasattr(self.app, 'usb') and self.app.usb is not None:`
   - USB object doesn't exist at sync time?
   - USB is a HAL adapter, not direct hardware?

3. **Method doesn't exist**: Neither `set_integration` nor `set_integration_time` exists
   - HAL adapter doesn't forward these methods?
   - Adapter created but methods not exposed?

4. **Silent failure**: Method called but doesn't actually change integration time
   - Hardware command fails silently?
   - Spectrometer doesn't respect the new integration time?

---

## Debug Strategy

### Added Debug Logging

Added extensive debug logging to `spr_state_machine.py:387-399`:
```python
# ✨ CRITICAL FIX: Apply the scaled integration time to the spectrometer
if hasattr(self.app, 'usb') and self.app.usb is not None:
    logger.info(f"🔍 DEBUG: USB object type: {type(self.app.usb)}")
    logger.info(f"🔍 DEBUG: USB has set_integration: {hasattr(self.app.usb, 'set_integration')}")
    logger.info(f"🔍 DEBUG: USB has set_integration_time: {hasattr(self.app.usb, 'set_integration_time')}")

    if hasattr(self.app.usb, 'set_integration'):
        self.app.usb.set_integration(live_integration_seconds)
        logger.info(f"✅ Applied scaled integration time to spectrometer: {live_integration_seconds*1000:.1f}ms")
    elif hasattr(self.app.usb, 'set_integration_time'):
        self.app.usb.set_integration_time(live_integration_seconds)
        logger.info(f"✅ Applied scaled integration time to spectrometer: {live_integration_seconds*1000:.1f}ms")
    else:
        logger.error(f"❌ Cannot set integration time - no suitable method found on USB object")
        logger.error(f"   Available methods: {[m for m in dir(self.app.usb) if not m.startswith('_')]}")
```

### Expected Debug Output

```
✅ Live mode integration scaled: 200.5ms → 100.3ms (factor=0.5)
🔍 DEBUG: USB object type: <class 'utils.spr_state_machine.DataAcquisitionWrapper.create_data_acquisition.<locals>.SpectrometerAdapter'>
🔍 DEBUG: USB has set_integration: False
🔍 DEBUG: USB has set_integration_time: True
✅ Applied scaled integration time to spectrometer: 100.3ms
```

OR (if failing):
```
❌ Cannot set integration time - no suitable method found on USB object
   Available methods: ['acquire_spectrum', 'read_intensity', 'get_wavelengths', ...]
```

---

## Potential Solutions

### Solution 1: Fix SpectrometerAdapter to Forward set_integration_time

If the adapter doesn't forward the method:
```python
# utils/spr_state_machine.py - SpectrometerAdapter class
class SpectrometerAdapter:
    """Adapter to make HAL spectrometer compatible with SPRDataAcquisition."""
    def __init__(self, hal_spectrometer):
        self.hal = hal_spectrometer

    def read_intensity(self):
        """Read intensity using HAL method."""
        if hasattr(self.hal, 'acquire_spectrum'):
            return self.hal.acquire_spectrum()
        # ...

    def set_integration_time(self, seconds):
        """Set integration time in seconds."""
        if hasattr(self.hal, 'set_integration_time'):
            return self.hal.set_integration_time(seconds)
        else:
            logger.error("HAL doesn't support set_integration_time")
            return False

    def __getattr__(self, name):
        """Forward other attributes to HAL."""
        return getattr(self.hal, name)
```

### Solution 2: Apply Integration Time Directly in Data Acquisition

Instead of setting once during init, set it before EVERY acquisition:
```python
# utils/spr_data_acquisition.py:_read_channel_data()
def _read_channel_data(self, ch: str) -> float:
    """Read and process data from a specific channel."""
    try:
        # ✨ Force integration time before each acquisition
        if hasattr(self, 'scaled_integration_time'):
            if hasattr(self.usb, 'set_integration_time'):
                self.usb.set_integration_time(self.scaled_integration_time)

        int_data_sum: np.ndarray | None = None
        self._activate_channel_batch(ch)
        # ...
```

### Solution 3: Remove LIVE_MODE_INTEGRATION_FACTOR, Use Calibrated Value

Store TWO integration times during calibration:
- `calibrated_integration`: For S-mode reference (200ms)
- `live_integration`: For P-mode live data (100ms)

Then no scaling needed in state machine - just use the right value.

---

## Next Steps

1. ✅ Run application with debug logging
2. ⏳ Check for debug output showing USB object type and methods
3. ⏳ Identify which solution path to take based on output
4. ⏳ Implement fix
5. ⏳ Verify P-mode intensity drops to ~26,000-30,000 counts

---

## Status

🔍 **Waiting for debug output from running application...**

Expected completion: After calibration finishes and transitions to live mode.
