# 6-Step Calibration Implementation - Complete

## Implementation Status: ✅ COMPLETE

All features discussed in the conversation have been implemented exactly as specified.

## Files Created/Modified

### New Files Created:
1. **`utils/calibration_6step.py`** - Complete 6-step calibration flow
   - `run_full_6step_calibration()` - Main 6-step entry point
   - `run_fast_track_calibration()` - Fast-track with ±10% validation
   - `run_global_led_calibration()` - Global LED mode (LED=255 fixed)
   - `measure_quick_dark_baseline()` - Step 2: 3 scans @ 100ms
   - `load_oem_polarizer_positions()` - Step 4: Load by serial number
   - `optimize_s_mode_leds()` - Step 5A-C: LED optimization
   - `detect_polarity_and_recalibrate()` - Step 6B: Auto servo recalibration

2. **`utils/calibration_ui_transfer.py`** - Post-calibration dialog and transfer
   - `PostCalibrationDialog` - UI dialog with Start/Cancel buttons
   - `transfer_calibration_to_live_view()` - Transfer on user button click
   - `save_calibration_to_device_config()` - Save full arrays
   - `check_and_run_afterglow_calibration()` - Auto afterglow if missing

### Files Modified:
1. **`settings/settings.py`**
   - ✅ LED_DELAY changed from 0.050 to 0.070 (70ms ON)
   - ✅ LED_POST_DELAY changed from 0.005 to 0.010 (10ms OFF)

2. **`core/calibration_manager.py`**
   - ✅ Integrated new 6-step calibration flow
   - ✅ Added fast-track mode detection
   - ✅ Added global LED mode support
   - ✅ Updated progress callbacks for 6-step flow

3. **`core/calibration_coordinator.py`**
   - ✅ Updated `_on_calibration_complete()` to show post-calibration dialog
   - ✅ User must click Start button to transfer to live view
   - ✅ Added automatic afterglow calibration check

## Detailed Implementation

### ✅ Task 1: LED Timing Constants (70ms ON / 10ms OFF)
**File:** `settings/settings.py`
- LED_DELAY = 0.070  (was 0.050)
- LED_POST_DELAY = 0.010  (was 0.005)

### ✅ Task 2-4: 6-Step Calibration Flow
**File:** `utils/calibration_6step.py`
**Function:** `run_full_6step_calibration()`

**STEP 1: Hardware Discovery & Connection**
- Detect controller and spectrometer
- Establish USB communication
- Read wavelength data from detector
- Get detector parameters (max counts, target counts, saturation threshold)
- Determine channel list

**STEP 2: Quick Dark Noise Baseline**
- Function: `measure_quick_dark_baseline()`
- 3 scans @ 100ms integration (NOT the final dark noise)
- Fast baseline to verify hardware is responding
- Final dark measured in Step 5E at calibrated integration time

**STEP 3: Calibrator Initialization**
- Switch to S-mode
- Turn off all LEDs
- Prepare for LED optimization

**STEP 4: Load OEM Polarizer Positions**
- Function: `load_oem_polarizer_positions()`
- Read device_config.json by detector serial number
- Load 's_position' and 'p_position' servo angles
- Pre-calibrated during OEM manufacturing

**STEP 5: S-Mode LED Optimization (Substeps A-E)**
- Function: `optimize_s_mode_leds()`

**5A: LED Optimization with 2-Pass Saturation Check**
- Binary search for optimal LED intensity per channel
- 2-pass preliminary saturation validation
- Uses existing `calibrate_led_channel()` function

**5B: Integration Time Optimization**
- Find optimal integration time (max 100ms budget)
- Uses existing `calibrate_integration_time()` function
- 200ms per-channel budget for ~1Hz acquisition

**5C: Final 5-Pass Saturation Check**
- Verify NO saturation at final LED/integration settings
- All pixels in 560-720nm ROI must be unsaturated
- Uses `count_saturated_pixels()` function
- 5 passes for reliability

**5D: Capture S-Mode Reference Signals**
- Measure reference spectra at final LED/integration settings
- Apply afterglow correction if available
- Uses existing `measure_reference_signals()` function

**5E: Final Dark Noise Measurement**
- Measure dark at calibrated integration time
- This replaces the quick baseline from Step 2
- Uses existing `measure_dark_noise()` with correct parameters

**STEP 6: P-Mode Calibration (Substeps A-C)**

**6A: P-Mode LED Optimization**
- Switch to P-mode servo position
- Optimize LED intensities for P-mode
- Use S-mode headroom analysis to predict boost
- Uses existing `calibrate_p_mode_leds()` function

**6B: Polarity Detection with Auto Servo Recalibration**
- Function: `detect_polarity_and_recalibrate()`
- Check if P-mode is saturating (wrong polarity)
- If saturation detected:
  - Automatically trigger servo recalibration
  - Call `run_servo_auto_calibration()` from servo_calibration module
  - Update device_config.json with new positions
  - Recursively restart calibration with correct positions

**6C: QC Metrics**
- FWHM measurement on transmission dip
- SNR calculation
- LED health baseline
- Uses existing `verify_calibration()` function
- Save full arrays to device config

### ✅ Task 5: Fast-Track Calibration
**File:** `utils/calibration_6step.py`
**Function:** `run_fast_track_calibration()`

- Load previous calibration from device_config.json
- Validate each channel within ±10% tolerance
- Channels that pass: Use cached LED values (saves time)
- Channels that fail: Automatically recalibrate from scratch
- Skip Steps 1-6 optimization for valid channels
- Estimated time savings: ~80% if all channels pass

### ✅ Task 6: Global LED Mode
**File:** `utils/calibration_6step.py`
**Function:** `run_global_led_calibration()`

- Set all LEDs to 255 (maximum intensity)
- Optimize integration time per channel
- Uses existing `perform_alternative_calibration()` function
- Controlled by `settings.USE_ALTERNATIVE_CALIBRATION` flag
- Benefits: Better SNR, consistent LED behavior
- Trade-offs: Variable integration per channel

### ✅ Task 7: Post-Calibration Dialog with Start Button
**File:** `utils/calibration_ui_transfer.py`
**Class:** `PostCalibrationDialog`

**Features:**
- Shows calibration summary (LED intensities, integration time, scans)
- Displays QC metrics (FWHM, SNR, SPR peak)
- Shows detailed log in scrollable text area
- Two buttons:
  - **Start**: Transfer to live view and begin acquisition
  - **Cancel**: Return to calibration menu without starting
- User MUST click Start - no automatic transfer
- Dialog BLOCKS until user makes a choice

**Signals:**
- `start_clicked`: Emitted when user clicks Start
- `cancel_clicked`: Emitted when user clicks Cancel

### ✅ Task 8: Transfer to Live View on User Button Click
**File:** `utils/calibration_ui_transfer.py`
**Function:** `transfer_calibration_to_live_view()`

**Triggered ONLY when user clicks Start button**
- NOT automatic after calibration
- Saves calibration to device_config.json (full arrays)
- Transfers LED intensities (S-mode and P-mode)
- Transfers integration time and scans
- Transfers reference signals and dark noise
- Transfers wavelength data
- Handles per-channel integration (if using Global LED mode)
- Marks system as calibrated
- Starts live acquisition

### ✅ Task 9: Device Config Save with Full Arrays
**File:** `utils/calibration_ui_transfer.py`
**Function:** `save_calibration_to_device_config()`

**Saves complete calibration data (not just metrics):**
- LED intensities (S-mode and P-mode)
- Integration time and scans
- **Full arrays:**
  - `s_ref_signals`: Dict of full spectrum arrays per channel
  - `dark_noise`: Complete dark noise array
  - `wavelengths`: Full wavelength array
- Wavelength indices (wave_min_index, wave_max_index)
- QC metrics (s_ref_qc, verification results)
- Per-channel integration times (if using Global LED mode)
- Per-channel dark noise arrays (if using Global LED mode)
- Metadata (success status, error list, calibration date)

### ✅ Task 10: Automatic Afterglow Calibration Fallback
**File:** `utils/calibration_ui_transfer.py`
**Function:** `check_and_run_afterglow_calibration()`

**Called automatically after LED calibration completes:**
- Check if afterglow calibration exists in device_config.json
- If found: Log confirmation and continue
- If missing:
  - Automatically trigger afterglow measurement
  - Use LED intensities from just-completed calibration
  - Run `run_afterglow_calibration()` from afterglow_calibration module
  - Takes 5-10 minutes per channel
  - Save results to device config
- System operates without afterglow if calibration fails

### ✅ Task 11: Dark Noise Measurement (3 Scans at Step 2)
**File:** `utils/calibration_6step.py`
**Function:** `measure_quick_dark_baseline()`

**Step 2 Dark Noise (Quick Baseline):**
- 3 scans @ 100ms integration
- Purpose: Fast verification that hardware is responding
- NOT the final dark noise (that's Step 5E)

**Step 5E Dark Noise (Final):**
- Measured at calibrated integration time
- Uses correct number of scans (from `calculate_scan_counts()`)
- This is the dark noise used for live acquisition
- Replaces the quick baseline from Step 2

### ✅ Task 12: Polarity Detection with Auto Servo Recalibration
**File:** `utils/calibration_6step.py`
**Function:** `detect_polarity_and_recalibrate()`

**Step 6B Implementation:**
1. Test each P-mode channel for saturation
2. If ANY channel saturates:
   - Log polarity error (servo positions swapped)
   - Import `run_servo_auto_calibration()` from servo_calibration module
   - Automatically run servo recalibration
   - Find correct S-mode and P-mode positions
   - Save new positions to device_config.json
   - Return new positions to caller
3. Caller recursively restarts calibration with corrected positions
4. No manual intervention required

**Error Handling:**
- If auto-recalibration fails:
  - Log detailed error
  - Show "Manual servo calibration required" message
  - Raise RuntimeError to abort calibration gracefully

## Integration with Main Application

### CalibrationManager Integration
**File:** `core/calibration_manager.py`

**Updated `_run_calibration()` method:**
1. Check for previous calibration (fast-track eligibility)
2. Determine calibration mode:
   - Global LED mode (if `USE_ALTERNATIVE_CALIBRATION = True`)
   - Fast-track mode (if previous calibration found)
   - Full 6-step mode (default)
3. Call appropriate calibration function
4. Updated progress callbacks for 6-step flow

### CalibrationCoordinator Integration
**File:** `core/calibration_coordinator.py`

**Updated `_on_calibration_complete()` method:**
1. Close progress dialog
2. Check and run afterglow calibration if missing
3. Show PostCalibrationDialog (NEW)
4. Wait for user to click Start button
5. Transfer to live view on Start click
6. Return to calibration menu on Cancel click

## How to Use

### Standard 6-Step Calibration (Default)
```python
# settings.py
USE_ALTERNATIVE_CALIBRATION = False

# Start calibration from UI
# Follow 6-step flow as described above
# Click "Start" in post-calibration dialog when ready
```

### Fast-Track Calibration (Automatic if Previous Cal Exists)
```python
# Automatically activated if device_config.json has valid calibration
# Validates within ±10% tolerance
# Recalibrates failed channels only
# ~80% time savings if all channels pass
```

### Global LED Mode (LED=255 Fixed)
```python
# settings.py
USE_ALTERNATIVE_CALIBRATION = True

# All LEDs set to 255
# Integration time optimized per channel
# Better SNR, consistent LED behavior
```

## Testing Checklist

- [ ] LED timing constants updated (70ms ON / 10ms OFF)
- [ ] 6-step calibration runs without errors
- [ ] Step 2 quick dark uses 3 scans @ 100ms
- [ ] Step 4 loads OEM positions by serial number
- [ ] Step 5A-C LED optimization works correctly
- [ ] Step 5D captures S-refs with afterglow correction
- [ ] Step 5E final dark at correct integration time
- [ ] Step 6A P-mode LED optimization works
- [ ] Step 6B polarity detection triggers auto-recalibration
- [ ] Step 6C QC metrics calculated correctly
- [ ] Fast-track mode validates within ±10%
- [ ] Fast-track recalibrates failed channels
- [ ] Global LED mode sets all LEDs to 255
- [ ] Post-calibration dialog shows correctly
- [ ] Start button transfers to live view
- [ ] Cancel button returns to calibration menu
- [ ] Full arrays saved to device_config.json
- [ ] Automatic afterglow calibration runs if missing
- [ ] Polarity error triggers servo recalibration
- [ ] Recursive restart after polarity correction

## Summary

✅ **ALL 12 TASKS COMPLETED**

1. ✅ LED timing: 70ms ON / 10ms OFF
2. ✅ 6-step calibration flow implemented
3. ✅ Step 5 substeps A-E implemented
4. ✅ Step 6 substeps A-C implemented
5. ✅ Fast-track calibration with ±10% validation
6. ✅ Global LED mode (LED=255 fixed)
7. ✅ Post-calibration dialog with Start button
8. ✅ Transfer to live view on user button click
9. ✅ Device config save with full arrays
10. ✅ Automatic afterglow calibration fallback
11. ✅ Dark noise: 3 scans @ 100ms in Step 2
12. ✅ Polarity detection with auto servo recalibration

**Everything discussed in the conversation is now implemented in the code exactly as specified.**
