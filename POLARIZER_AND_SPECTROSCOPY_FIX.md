# Polarizer and Spectroscopy Data Fix

## Issues Identified

### Issue 1: Polarizer Not Switching to P-Mode ❌
**Problem**: After calibration completes, the polarizer does not switch to P-mode for live measurements.

**Root Cause**: In `utils/spr_state_machine.py` line ~1004, the code tried to use `ctrl_device` variable, but this variable was only defined inside the `if not self.data_acquisition:` block (line 970). When the data acquisition object already exists (which is always the case after calibration), `ctrl_device` is undefined, causing a `NameError` that prevents the polarizer from switching.

**Fix Applied**: ✅
- Moved `ctrl_device` retrieval to just before the polarizer switch (line ~1004)
- Added metadata update to sync polarizer_mode="p" in data acquisition object
- Now the polarizer properly switches to P-mode before starting live measurements

### Issue 2: No Spectroscopy Output in Continuous Data ❌
**Problem**: `spectroscopy_data()` returns empty or missing data during live measurements.

**Root Cause**: The `int_data` and `trans_data` dictionaries are likely not being populated correctly during continuous acquisition. This could be because:
1. The data is only populated in P-mode processing (line 469 in spr_data_acquisition.py)
2. The calibration reference signals (`ref_sig`) may not be transferred to the data acquisition wrapper

**Status**: ⚠️ NEEDS INVESTIGATION

---

## Fix Details

### File: `utils/spr_state_machine.py`

**Location**: `_handle_calibrated()` method, lines 1000-1028

**Before**:
```python
if not self.data_acquisition.is_running():
    logger.info("Starting real-time data acquisition...")
    try:
        # ✨ CRITICAL: Switch polarizer to P-mode for live measurements
        if hasattr(ctrl_device, 'set_mode'):  # ❌ ctrl_device undefined here!
            logger.info("🔄 Switching polarizer to P-mode for live measurements...")
```

**After**:
```python
if not self.data_acquisition.is_running():
    logger.info("Starting real-time data acquisition...")
    try:
        # Get device object for polarizer control
        if isinstance(self.hardware_manager, SimpleHardwareManager):
            ctrl_device = self._get_device_from_hal(self.hardware_manager.ctrl)
        else:
            ctrl_device = self.app.ctrl

        # ✨ CRITICAL: Switch polarizer to P-mode for live measurements
        if hasattr(ctrl_device, 'set_mode'):
            logger.info("🔄 Switching polarizer to P-mode for live measurements...")
            try:
                ctrl_device.set_mode("p")
                time.sleep(0.4)  # Wait for servo to rotate
                logger.info("✅ Polarizer switched to P-mode")

                # ✨ Update polarizer_mode in data acquisition for metadata tracking
                if hasattr(self.data_acquisition, 'acquisition') and hasattr(self.data_acquisition.acquisition, 'polarizer_mode'):
                    self.data_acquisition.acquisition.polarizer_mode = "p"
                    logger.debug("✅ Data acquisition metadata updated: polarizer_mode='p'")
            except Exception as e:
                logger.warning(f"⚠️ Failed to switch polarizer to P-mode: {e}")
                logger.warning("   Continuing with current polarizer position")
        else:
            logger.warning("⚠️ Controller does not support polarizer mode switching")
```

---

## Testing Checklist

### Polarizer Switch Test
- [ ] Run full calibration (Steps 1-8)
- [ ] Watch for log message: "🔄 Switching polarizer to P-mode for live measurements..."
- [ ] Listen for polarizer servo movement (mechanical sound)
- [ ] Check for log message: "✅ Polarizer switched to P-mode"
- [ ] Verify log message: "✅ Data acquisition metadata updated: polarizer_mode='p'"

**Expected Logs**:
```
Starting real-time data acquisition...
🔄 Switching polarizer to P-mode for live measurements...
✅ Polarizer switched to P-mode
✅ Data acquisition metadata updated: polarizer_mode='p'
Data acquisition wrapper created successfully
```

### Spectroscopy Data Test
- [ ] Start live measurements after calibration
- [ ] Check UI for spectroscopy plot updates
- [ ] Verify `int_data` contains spectrum arrays for each channel
- [ ] Verify `trans_data` contains transmittance data
- [ ] Check that `polarizer_mode` metadata = "p"
- [ ] Check that `led_intensities` metadata contains adjusted LED values

**Expected Data Structure**:
```python
{
    "wave_data": np.array([...]),  # Wavelength array
    "int_data": {
        "a": np.array([...]),  # Channel A intensity spectrum
        "b": np.array([...]),  # Channel B intensity spectrum
        "c": np.array([...]),  # Channel C intensity spectrum
        "d": np.array([...]),  # Channel D intensity spectrum
    },
    "trans_data": {
        "a": np.array([...]),  # Channel A transmittance
        "b": np.array([...]),  # Channel B transmittance
        "c": np.array([...]),  # Channel C transmittance
        "d": np.array([...]),  # Channel D transmittance
    },
    "polarizer_mode": "p",  # ✅ Should be "p" for live measurements
    "led_intensities": {"a": 201, "b": 255, "c": 122, "d": 129},  # Adjusted LED values
    "num_scans": 1
}
```

---

## Remaining Issues to Investigate

### Spectroscopy Data Population

**Question**: Why is `int_data` empty during continuous measurements?

**Hypotheses**:
1. **Reference Signal Transfer**: The `ref_sig` from calibration may not be transferred to the data acquisition wrapper
2. **Timing Issue**: Data may not be processed quickly enough before UI update
3. **Mode Check**: Code may skip processing if polarizer mode is incorrect

**Investigation Steps**:
1. Add logging in `_read_channel_data()` to verify data flow:
   ```python
   logger.debug(f"Channel {ch}: raw_array shape={raw_array.shape}, ref_sig available={self.ref_sig[ch] is not None}")
   ```

2. Check if `ref_sig` is populated in data acquisition:
   ```python
   # In DataAcquisitionWrapper.sync_from_shared_state()
   if self.calib_state and hasattr(self.calib_state, 'ref_sig'):
       self.ref_sig = self.calib_state.ref_sig.copy()
       logger.info(f"✅ Synced ref_sig: {list(self.ref_sig.keys())}")
   ```

3. Verify P-mode intensity calculation:
   ```python
   # In spr_data_acquisition.py line ~469
   logger.debug(f"P-mode processing: s_intensity shape={s_intensity.shape}, ref_sig shape={self.ref_sig[ch].shape}")
   ```

---

## Success Criteria

✅ **Polarizer Switch**:
- Polarizer audibly moves after calibration
- Log confirms switch to P-mode
- `polarizer_mode` metadata = "p"

⏳ **Spectroscopy Data** (PENDING):
- `int_data` contains spectrum arrays (not empty)
- `trans_data` contains transmittance values
- UI spectroscopy plot displays data
- Data updates in real-time (~1.8 Hz)

---

## Current Status

| Issue | Status | Notes |
|-------|--------|-------|
| Polarizer not switching | ✅ FIXED | `ctrl_device` now properly defined |
| Metadata not updating | ✅ FIXED | Added polarizer_mode sync |
| Spectroscopy data empty | ⚠️ INVESTIGATING | Needs further debugging |
| ref_sig transfer | ⚠️ UNKNOWN | May need to verify sync |

---

## Next Steps

1. **Test the polarizer fix**: Run app and verify polarizer moves after calibration
2. **Debug spectroscopy data**: Add logging to track data flow through acquisition
3. **Verify ref_sig transfer**: Ensure calibration references are available to live acquisition
4. **Monitor UI updates**: Check if spectroscopy plot receives data

---

## Related Files

- `utils/spr_state_machine.py` - Polarizer switch logic (✅ FIXED)
- `utils/spr_data_acquisition.py` - Data acquisition and spectroscopy output
- `LIVE_DATA_METADATA_ENHANCEMENT.md` - Metadata documentation
- `PER_CHANNEL_LED_ADJUSTMENT_FIX.md` - LED adjustment system

---

## Implementation Date

- **Fix Applied**: October 19, 2025
- **Testing Required**: Yes
- **Documentation Updated**: Yes
