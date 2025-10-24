# Live Boost Parameters Saved to Device Config (QC Validation)

## Summary
Updated the calibration workflow to save the **live-boosted S-ref spectra** and boost parameters to `device_config.json`. This ensures QC validation compares against the actual running baseline, not the calibration baseline.

## Problem
Previously:
- Calibration saved S-ref at **calibration baseline** settings (e.g., 150ms integration)
- Live mode applied **boost** (e.g., 1.5× → 200ms integration, reduced bright LED intensities)
- QC validation compared against **wrong baseline** (calibration, not live)

This caused QC validation to fail or give incorrect results because the reference didn't match actual running conditions.

## Solution
Modified `utils/spr_state_machine.py` to:
1. **Re-capture S-ref spectra** after boost is applied (but before switching to P-mode)
2. **Save boosted S-ref** + boost parameters to `device_config.json`
3. Future QC validations will compare against the **correct live baseline**

## Calibration Flow (Updated)

```
┌─────────────────────────────────────────────────────────────┐
│ Step 1-7: S-mode Calibration (spr_calibrator.py)           │
│   - Dark noise measurement                                  │
│   - Find weakest LED (Step 3)                              │
│   - Optimize integration time for weakest @ 255 (Step 4)   │
│   - Binary search LED calibration (Step 6)                 │
│   - Measure S-ref at CALIBRATION baseline (Step 7)         │
│   - Save to device_config (OVERWRITTEN later)              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Transition to CALIBRATED State (spr_state_machine.py)      │
│   - Create DataAcquisitionWrapper                          │
│   - Sync calibration state                                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ ✨ Apply Smart Boost (DataAcquisitionWrapper.__init__)     │
│   - Calculate boost factor (e.g., 1.5× for 60% target)     │
│   - Increase integration time (150ms → 200ms)              │
│   - Reduce bright LED intensities per-channel              │
│   - Store: live_integration_seconds, live_boost_factor,    │
│            live_led_intensities                            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ ✨ NEW: Re-capture S-ref with Boosted Settings             │
│   - Stay in S-mode                                         │
│   - Apply boosted integration time to spectrometer         │
│   - Measure each channel with adjusted LED intensities     │
│   - Save boosted S-ref + boost params to device_config     │
│   - This OVERWRITES the calibration baseline save          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Switch to P-mode                                           │
│   - Rotate polarizer servo (400ms settling)                │
│   - Update metadata                                        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Start Live Data Acquisition                                │
│   - Real-time P-pol measurements                           │
│   - Uses boosted integration time + adjusted LEDs          │
└─────────────────────────────────────────────────────────────┘
```

## Code Changes

### 1. `utils/spr_state_machine.py` (DataAcquisitionWrapper.__init__)
**Lines 432-433**: Store boost parameters as instance variables
```python
# ✨ Store boost parameters for later use (S-ref recapture and device config save)
self.live_integration_seconds = live_integration_seconds
self.live_boost_factor = actual_boost
```

### 2. `utils/spr_state_machine.py` (_handle_calibrated)
**Lines 1103-1185**: Re-capture S-ref with boosted settings and save
```python
# ✨ NEW: Re-capture S-ref spectra with BOOSTED settings (BEFORE switching to P-mode)
# This ensures QC validation compares against the actual live mode baseline
if self.data_acquisition and hasattr(self.data_acquisition, 'live_led_intensities') and self.data_acquisition.live_led_intensities:
    logger.info("=" * 80)
    logger.info("📸 RE-CAPTURING S-REF WITH BOOSTED SETTINGS (for QC validation)")
    logger.info("=" * 80)
    try:
        # Get hardware devices
        if isinstance(self.hardware_manager, SimpleHardwareManager):
            ctrl_device = self._get_device_from_hal(self.hardware_manager.ctrl)
            usb_device = self._get_device_from_hal(self.hardware_manager.usb)
        else:
            ctrl_device = self.app.ctrl
            usb_device = self.app.usb

        # Ensure we're in S-mode
        if hasattr(ctrl_device, 'set_mode'):
            ctrl_device.set_mode("s")
            time.sleep(0.4)  # Wait for servo

        # Apply boosted integration time to spectrometer
        live_integration_seconds = getattr(self.data_acquisition, 'live_integration_seconds', self.calib_state.integration)
        if hasattr(usb_device, 'set_integration'):
            usb_device.set_integration(live_integration_seconds)
        elif hasattr(usb_device, 'set_integration_time'):
            usb_device.set_integration_time(live_integration_seconds)
        time.sleep(0.1)

        # Measure S-ref with boosted settings for each channel
        boosted_s_ref = {}
        ch_list = ['a', 'b', 'c', 'd']

        for ch in ch_list:
            boosted_led = self.data_acquisition.live_led_intensities.get(ch, 255)
            ctrl_device.set_led(ch, boosted_led)
            time.sleep(0.1)  # LED settling time
            spectrum = usb_device.get_spectrum()
            boosted_s_ref[ch] = spectrum
            ctrl_device.set_led(ch, 0)

        # Save to device_config with boost parameters
        device_config.save_led_calibration(
            integration_time_ms=int(self.calib_state.integration * 1000),  # Calibration baseline
            s_mode_intensities=self.calib_state.ref_intensity.copy(),
            p_mode_intensities=self.calib_state.ref_intensity.copy(),
            s_ref_spectra=boosted_s_ref,  # ✨ Use boosted S-ref
            s_ref_wavelengths=self.calib_state.wavelengths,
            live_boost_integration_ms=live_integration_ms,  # ✨ Boosted integration time
            live_boost_led_intensities=self.data_acquisition.live_led_intensities.copy(),  # ✨ Adjusted LEDs
            live_boost_factor=live_boost_factor  # ✨ Boost multiplier
        )

    except Exception as e:
        logger.exception(f"❌ Failed to re-capture S-ref with boosted settings: {e}")
        logger.warning("   Continuing with calibration baseline S-ref")
```

### 3. `utils/device_configuration.py` (save_led_calibration)
**Lines 506-590**: Already updated in previous session to accept boost parameters
```python
def save_led_calibration(
    self,
    integration_time_ms: int,
    s_mode_intensities: Dict[str, int],
    p_mode_intensities: Dict[str, int],
    s_ref_spectra: Dict[str, Any],
    s_ref_wavelengths: Optional[Any] = None,
    live_boost_integration_ms: Optional[int] = None,  # ✨ NEW
    live_boost_led_intensities: Optional[Dict[str, int]] = None,  # ✨ NEW
    live_boost_factor: Optional[float] = None  # ✨ NEW
) -> None:
```

## Device Config Structure (Updated)

```json
{
  "led_calibration": {
    "timestamp": "2025-01-24T10:30:45",
    "integration_time_ms": 150,
    "s_mode_intensities": {"a": 255, "b": 200, "c": 70, "d": 55},
    "p_mode_intensities": {"a": 255, "b": 200, "c": 70, "d": 55},
    "s_ref_spectra": {
      "a": [...],
      "b": [...],
      "c": [...],
      "d": [...]
    },
    "s_ref_wavelengths": [...],
    "live_boost_integration_ms": 200,
    "live_boost_led_intensities": {"a": 255, "b": 200, "c": 60, "d": 48},
    "live_boost_factor": 1.33
  }
}
```

## Example Log Output

```
================================================================================
📸 RE-CAPTURING S-REF WITH BOOSTED SETTINGS (for QC validation)
================================================================================
   Integration time: 200.0ms (boosted)
   Channel A: LED=255, avg signal=32000
   Channel B: LED=200, avg signal=30000
   Channel C: LED=60, avg signal=28000
   Channel D: LED=48, avg signal=29000
✅ S-ref re-captured with boosted settings
================================================================================
💾 SAVING BOOSTED CALIBRATION TO DEVICE CONFIG
================================================================================
✅ Boosted calibration saved to device_config.json
   Calibration baseline: 150ms
   Live boost: 200ms (1.33×)
   Live LED adjustments: {'a': 255, 'b': 200, 'c': 60, 'd': 48}
================================================================================
```

## QC Validation Workflow

### On Subsequent Startups:
1. Load `device_config.json`
2. Extract **live_boost_integration_ms** and **live_boost_led_intensities**
3. Measure current S-ref using **LIVE BOOST SETTINGS** (not calibration baseline)
4. Compare against saved boosted S-ref spectra
5. QC pass/fail based on deviation threshold

### Why This Works:
- **Calibration baseline** (150ms, LED [255,200,70,55]) is too conservative for QC
- **Live boost** (200ms, LED [255,200,60,48]) matches actual running conditions
- QC compares "live now" vs "live reference" → correct validation

## Testing Checklist

- [ ] Run fresh calibration and verify:
  - [ ] Calibration Steps 1-7 complete successfully
  - [ ] Smart boost applied (check log for boost factor)
  - [ ] S-ref re-captured with boosted settings (check log)
  - [ ] `device_config.json` contains live boost parameters
  - [ ] Polarizer switches to P-mode after S-ref save
  - [ ] Live acquisition starts successfully

- [ ] Verify device_config.json structure:
  - [ ] `led_calibration.integration_time_ms` = calibration baseline (e.g., 150)
  - [ ] `led_calibration.live_boost_integration_ms` = boosted value (e.g., 200)
  - [ ] `led_calibration.live_boost_led_intensities` = adjusted LEDs
  - [ ] `led_calibration.live_boost_factor` = boost multiplier (e.g., 1.33)
  - [ ] `led_calibration.s_ref_spectra` = boosted S-ref (NOT calibration baseline)

- [ ] Test QC validation on next startup:
  - [ ] Restart application
  - [ ] QC should load boosted baseline from device_config
  - [ ] QC should measure current S-ref with live boost settings
  - [ ] QC comparison should use correct baseline

## Benefits

✅ **Correct QC validation** - Compares like-to-like (live vs live, not live vs calibration)
✅ **No code duplication** - Smart boost logic remains in one place
✅ **Automatic workflow** - No manual intervention needed
✅ **Backward compatible** - Falls back to calibration baseline if boost params missing
✅ **Clear logging** - Easy to verify boost was applied and saved

## Related Files

- `utils/spr_state_machine.py` - Re-capture and save logic
- `utils/device_configuration.py` - Save method signature
- `CALIBRATION_DATA_PERSISTENCE_COMPLETE.md` - Original device_config implementation
- `P_MODE_S_BASED_CALIBRATION.md` - Smart boost documentation
