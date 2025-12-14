# Dual Calibration Modes Implementation - COMPLETE

## Overview

Successfully implemented two distinct calibration modes for the SPR system, providing flexibility for different use cases and hardware configurations.

## Implementation Date
October 24, 2025

## Calibration Modes

### Mode 1: GLOBAL (Traditional)
**Purpose:** Balanced signal levels across channels with global integration time

**Workflow:**
1. Step 1: Measure baseline dark noise
2. Step 2: Calibrate wavelength range + **Mode selection display**
3. Step 3: Rank LEDs by brightness (weakest → strongest)
4. Step 4: Optimize integration time for weakest LED @ 255
5. Step 5: Re-measure dark noise at final integration time
6. Step 6: Balance other LEDs by reducing intensity to match weakest
7. Step 7: Measure S-mode references with calibrated LED intensities

**Characteristics:**
- LED intensities calibrated per channel (typically 50-255)
- Single global integration time for all channels
- All channels achieve similar signal levels (within 15%)
- Best for balanced performance across channels

### Mode 2: PER_CHANNEL (Advanced)
**Purpose:** Maximum flexibility with per-channel integration times

**Workflow:**
1. Step 1: Measure baseline dark noise
2. Step 2: Calibrate wavelength range + **Mode selection display**
3. Step 3: Rank LEDs by brightness (weakest → strongest)
4. **Step 4: SKIPPED** - All LEDs set to 255 (no LED calibration)
5. Step 5: Re-measure dark noise
6. **Step 6: SKIPPED** - No LED balancing needed
7. **Step 6.5: NEW** - Optimize integration time per channel (LED=255)
8. Step 7: Measure S-mode references with per-channel integration times

**Characteristics:**
- All LEDs fixed at maximum intensity (255)
- Integration time optimized independently per channel
- Each channel reaches 50-75% of detector max
- 200ms budget per channel (scan averaging if needed)
- Similar to s-roi-stability-test mode
- Best for widely varying channel responses

## Mode Selection

### How to Select Mode
```python
# Before running calibration
calibrator.set_calibration_mode('global')      # Traditional mode (default)
calibrator.set_calibration_mode('per_channel') # Advanced mode
```

### Mode Display in Step 2
```
================================================================================
CALIBRATION MODE SELECTION
================================================================================
Current mode: GLOBAL

Available modes:
  1. GLOBAL (default)
     • Step 4 calibrates LED intensities per channel
     • Uses single global integration time
     • Best for balanced signal levels

  2. PER_CHANNEL (advanced)
     • All LEDs fixed at 255 (maximum)
     • Uses per-channel integration times
     • Optimal for widely varying channel responses
     • Similar to s-roi-stability-test mode

Mode can be changed programmatically using:
  calibrator.set_calibration_mode('global' or 'per_channel')
================================================================================
```

## Code Changes

### 1. CalibrationState (spr_calibrator.py)
```python
# Line ~251: Added calibration mode field
self.calibration_mode: str = 'global'  # or 'per_channel'

# Line ~253-254: Already had per-channel storage
self.integration_per_channel: dict[str, float] = dict.fromkeys(CH_LIST, MIN_INTEGRATION / MS_TO_SECONDS)
self.scans_per_channel: dict[str, int] = dict.fromkeys(CH_LIST, 1)
```

### 2. Mode Setter Method (spr_calibrator.py)
```python
# Line ~850: Added set_calibration_mode method
def set_calibration_mode(self, mode: str) -> bool:
    """Set calibration mode: 'global' or 'per_channel'."""
    if mode not in ['global', 'per_channel']:
        logger.error(f"Invalid calibration mode: {mode}")
        return False
    
    self.state.calibration_mode = mode
    logger.info(f"📊 Calibration mode set to: {mode.upper()}")
    
    if mode == 'global':
        logger.info("   • Step 4: LED calibration + global integration time")
        logger.info("   • Step 6: LED balancing")
    else:
        logger.info("   • All LEDs fixed at 255")
        logger.info("   • Per-channel integration times")
    
    return True
```

### 3. Step 2: Mode Selection Display (spr_calibrator.py)
```python
# Line ~1815-1838: Added mode selection display
logger.info("=" * 80)
logger.info("CALIBRATION MODE SELECTION")
logger.info("=" * 80)
logger.info(f"Current mode: {self.state.calibration_mode.upper()}")
logger.info("")
logger.info("Available modes:")
logger.info("  1. GLOBAL (default)")
logger.info("     • Step 4 calibrates LED intensities per channel")
logger.info("     • Uses single global integration time")
logger.info("     • Best for balanced signal levels")
logger.info("")
logger.info("  2. PER_CHANNEL (advanced)")
logger.info("     • All LEDs fixed at 255 (maximum)")
logger.info("     • Uses per-channel integration times")
logger.info("     • Optimal for widely varying channel responses")
logger.info("     • Similar to s-roi-stability-test mode")
logger.info("")
logger.info("Mode can be changed programmatically using:")
logger.info("  calibrator.set_calibration_mode('global' or 'per_channel')")
logger.info("=" * 80)
```

### 4. Step 4: Skip LED Calibration in Per-Channel Mode (spr_calibrator.py)
```python
# Line ~2600-2630: Check calibration mode at start of step 4
if self.state.calibration_mode == 'per_channel':
    logger.info(f"")
    logger.info(f"=" * 80)
    logger.info(f"⚡ STEP 4: PER-CHANNEL MODE - SKIPPING LED CALIBRATION")
    logger.info(f"=" * 80)
    logger.info(f"   Mode: PER_CHANNEL (all LEDs fixed at 255)")
    logger.info(f"   Step 4 → SKIPPED (no LED calibration needed)")
    logger.info(f"   Step 6 → SKIPPED (no LED balancing needed)")
    logger.info(f"")
    logger.info(f"   Setting all LEDs to maximum intensity (255)...")
    
    # Set all LEDs to 255
    ch_list = self.state.led_ranking if self.state.led_ranking else [('a', (0,)), ('b', (0,)), ('c', (0,)), ('d', (0,))]
    for ch_info in ch_list:
        ch = ch_info[0]
        self.ctrl.set_intensity(ch, MAX_LED_INTENSITY)
        self.state.led_intensities[ch] = MAX_LED_INTENSITY
    
    logger.info(f"   ✅ All LEDs set to 255")
    self.ctrl.turn_off_channels()
    return True
```

### 5. Step 6: Skip LED Balancing in Per-Channel Mode (spr_calibrator.py)
```python
# Line ~3190-3205: Check calibration mode at start of step 6
if self.state.calibration_mode == 'per_channel':
    logger.info("")
    logger.info("=" * 80)
    logger.info("🔧 STEP 6: PER-CHANNEL MODE - SKIPPING LED BALANCING")
    logger.info("=" * 80)
    logger.info(f"   Mode: PER_CHANNEL (all LEDs already at 255)")
    logger.info(f"   LED balancing not needed in per-channel mode")
    logger.info(f"")
    logger.info(f"   ✅ All LEDs remain at 255")
    logger.info(f"   Next: Step 7 will optimize per-channel integration times")
    logger.info("=" * 80)
    return True
```

### 6. Step 6.5: Per-Channel Integration Optimizer (spr_calibrator.py)
```python
# Line ~3370-3545: New method optimize_per_channel_integration_times
def optimize_per_channel_integration_times(self, ch_list: list[str]) -> bool:
    """Optimize integration time for each channel independently (per_channel mode).
    
    Each channel gets its own integration time to reach 50-75% of detector max.
    The 200ms budget is applied per-channel with scan averaging if needed.
    """
    # Binary search per channel
    for ch in ch_list:
        integration_min = min_int
        integration_max = max_int
        
        # Find optimal integration time
        for iteration in range(max_iterations):
            test_integration = (integration_min + integration_max) / 2.0
            self.usb.set_integration(test_integration)
            
            # Measure at LED=255
            result = self._measure_channel_in_roi(ch, MAX_LED_INTENSITY, ...)
            signal_max, _ = result
            
            # Adjust search range
            if target_min <= signal_max <= target_max:
                best_integration = test_integration
                break
            elif signal_max < target_min:
                integration_min = test_integration
            else:
                integration_max = test_integration
        
        # Apply 200ms budget (scan averaging if needed)
        integration_ms = best_integration * 1000
        if integration_ms <= 200.0:
            num_scans = 1
        else:
            num_scans = int(np.ceil(integration_ms / 200.0))
            best_integration = 200.0 / 1000 / num_scans
        
        # Store per-channel parameters
        self.state.integration_per_channel[ch] = best_integration
        self.state.scans_per_channel[ch] = num_scans
    
    return True
```

### 7. Main Calibration Flow: Call Per-Channel Optimizer (spr_calibrator.py)
```python
# Line ~5115-5125: Added per-channel optimization after step 6
# STEP 6: BALANCE LED INTENSITIES
success = self.step_6_balance_led_intensities(ch_list)
if not success or self._is_stopped():
    return False, "Step 6: LED balancing failed"

# PER-CHANNEL MODE: OPTIMIZE INTEGRATION TIMES
if self.state.calibration_mode == 'per_channel':
    self._emit_progress(6.5, "Optimizing per-channel integration times...")
    success = self.optimize_per_channel_integration_times(ch_list)
    if not success or self._is_stopped():
        return False, "Per-channel integration optimization failed"

# STEP 7: REFERENCE SIGNAL MEASUREMENT
```

### 8. Step 7: Use Per-Channel Integration Times (spr_calibrator.py)
```python
# Line ~4465-4510: Updated step 7 for per-channel mode
def step_7_measure_reference_signals(self, ch_list: list[str]) -> bool:
    """Measure S-mode references with appropriate parameters per mode."""
    
    # Determine parameters based on mode
    if self.state.calibration_mode == 'per_channel':
        logger.info(f"   Mode: PER_CHANNEL (using per-channel integration times)")
    else:
        logger.info(f"   Mode: GLOBAL (using global integration time)")
        ref_scans = calculate_dynamic_scans(self.state.integration)
    
    for ch in ch_list:
        # Set per-channel integration time if in per_channel mode
        if self.state.calibration_mode == 'per_channel':
            ch_integration = self.state.integration_per_channel[ch]
            ch_scans = self.state.scans_per_channel[ch]
            self.usb.set_integration(ch_integration)
            ref_scans = ch_scans
        
        # Set LED intensity based on mode
        if self.state.calibration_mode == 'per_channel':
            intensities_dict = {ch: MAX_LED_INTENSITY}  # LED=255
        else:
            intensities_dict = {ch: self.state.ref_intensity[ch]}  # Calibrated
        
        # Acquire reference
        averaged_signal = self._acquire_averaged_spectrum(
            num_scans=ref_scans,
            apply_jitter_correction=True
        )
```

### 9. Live Data Acquisition: Per-Channel Integration Support (spr_data_acquisition.py)
```python
# Line ~320: Added per-channel integration dictionary
self.integration_per_channel: dict[str, float] = {}  # Per-channel integration times

# Line ~830-845: Set per-channel integration in _acquire_raw_spectrum
def _acquire_raw_spectrum(self, ch: str):
    """Acquire spectrum with per-channel integration if available."""
    
    # Set per-channel integration time if available
    if hasattr(self, 'integration_per_channel') and ch in self.integration_per_channel:
        ch_integration = self.integration_per_channel[ch]
        if hasattr(self.usb, 'set_integration'):
            self.usb.set_integration(ch_integration)
            time.sleep(0.05)
        elif hasattr(self.usb, 'set_integration_time'):
            self.usb.set_integration_time(ch_integration)
            time.sleep(0.05)
    
    # Use per-channel scan count
    scans_for_channel = self.scans_per_channel.get(ch, self.num_scans)
```

### 10. State Machine: Transfer Per-Channel Settings (spr_state_machine.py)
```python
# Line ~285-290: Pass per-channel integration times to data acquisition
if self.calib_state is not None and hasattr(self.calib_state, 'integration_per_channel'):
    self.data_acquisition.integration_per_channel = self.calib_state.integration_per_channel.copy()
    logger.info("✅ Passed per-channel integration times to data acquisition:")
    for ch, integration in self.calib_state.integration_per_channel.items():
        logger.info(f"   Channel {ch.upper()}: {integration*1000:.1f}ms")
```

## Testing Recommendations

### Global Mode Testing
1. Run calibration with `calibrator.set_calibration_mode('global')`
2. Verify Step 4 optimizes integration time
3. Verify Step 6 balances LED intensities
4. Check all channels reach 50-75% detector max
5. Confirm similar signal levels across channels

### Per-Channel Mode Testing
1. Run calibration with `calibrator.set_calibration_mode('per_channel')`
2. Verify Step 4 skips LED calibration
3. Verify Step 6 skips LED balancing
4. Verify Step 6.5 optimizes per-channel integration
5. Check each channel reaches 50-75% detector max independently
6. Confirm LEDs remain at 255 throughout

### Live Data Acquisition Testing
1. After calibration, start live measurements
2. Verify per-channel integration times are applied
3. Verify per-channel scan counts are used
4. Check that data quality is maintained
5. Monitor timing to ensure 200ms budget per channel

## Benefits

### Global Mode
✅ Balanced signal levels across channels  
✅ Single integration time simplifies timing  
✅ Consistent LED power consumption  
✅ Traditional, well-tested approach  

### Per-Channel Mode
✅ Maximum LED brightness for all channels  
✅ Optimal signal level per channel independently  
✅ Handles widely varying channel responses  
✅ Flexible integration times per channel  
✅ Similar to proven s-roi-stability-test mode  
✅ Better for channels with very different LED brightnesses  

## Files Modified

1. **utils/spr_calibrator.py** (5761 lines)
   - Added calibration_mode field to CalibrationState
   - Added set_calibration_mode() method
   - Added mode selection display in step_2
   - Modified step_4 to skip LED calibration in per_channel mode
   - Modified step_6 to skip LED balancing in per_channel mode
   - Added optimize_per_channel_integration_times() method
   - Updated step_7 to use per-channel parameters
   - Integrated per-channel optimizer into main calibration flow

2. **utils/spr_data_acquisition.py** (1697 lines)
   - Added integration_per_channel dictionary
   - Modified _acquire_raw_spectrum to set per-channel integration
   - Uses scans_per_channel for averaging

3. **utils/spr_state_machine.py** (1442 lines)
   - Added transfer of integration_per_channel from calibrator to data acquisition
   - Logs per-channel integration times on transfer

## Status

✅ **COMPLETE** - All components implemented and integrated

### Implementation Checklist
- [x] Add calibration_mode field to CalibrationState
- [x] Create set_calibration_mode() method with validation
- [x] Add mode selection display in Step 2
- [x] Modify Step 4 to skip LED calibration in per_channel mode
- [x] Modify Step 6 to skip LED balancing in per_channel mode
- [x] Create optimize_per_channel_integration_times() method
- [x] Integrate per-channel optimizer into main calibration flow
- [x] Update Step 7 to use per-channel parameters
- [x] Add per-channel integration support in live data acquisition
- [x] Transfer per-channel settings from calibrator to data acquisition

## Next Steps

1. **User Testing**
   - Test both modes with real hardware
   - Compare signal quality between modes
   - Validate timing performance

2. **Documentation**
   - Update user guide with mode selection instructions
   - Add examples for each mode
   - Document when to use each mode

3. **Optional Enhancements**
   - Add mode selection to GUI (currently programmatic only)
   - Save preferred mode in device config
   - Add mode comparison tool

## Related Documents

- `SIMPLIFIED_ARCHITECTURE_README.md` - Overall system architecture
- `CALIBRATION_ACCELERATION_GUIDE.md` - Calibration flow optimization
- `DETECTOR_PROFILES_IMPLEMENTATION.md` - Detector-specific parameters
- `P_MODE_S_BASED_CALIBRATION.md` - S-mode calibration strategy

---
**Implementation Complete:** October 24, 2025  
**Status:** Ready for testing
