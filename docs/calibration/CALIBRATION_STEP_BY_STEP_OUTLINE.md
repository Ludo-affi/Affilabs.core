# SPR System Calibration - Step-by-Step Outline

**Source**: `utils/spr_calibrator.py` → `run_full_calibration()`
**Date**: October 11, 2025
**Purpose**: Comprehensive breakdown of the 9-step calibration sequence

---

## Calibration Architecture

### Entry Point
```
main.py
  → SPRStateMachine._process_calibrating()
  → SPRCalibrator.start_calibration()
  → SPRCalibrator.run_full_calibration()
```

### State Management
- **Shared Calibration State**: Single source of truth (`CalibrationState`)
- **Progress Signals**: `calibration_progress(step, description)`
- **Completion Signals**: `calibration_completed(success, error_msg)`
- **Fresh Start**: Always clears legacy data unless `use_previous_data=True` (disabled by default)

---

## The 9 Calibration Steps

### **STEP 0: Detector Profile Loading** 📊
```python
# Auto-detect spectrometer and load detector-specific parameters
detector_profile = detector_manager.auto_detect(spectrometer)
```

**Purpose**: Load hardware-specific calibration parameters
**What It Does**:
- Auto-detects spectrometer (Flame-T, USB4000, etc.)
- Loads detector profile with:
  - Pixel count
  - Wavelength range (min/max)
  - Max intensity (65535 counts typically)
  - Target signal (40000 ± 10000 counts for Flame-T)
  - SPR wavelength range (500-900nm typically)
  - Max integration time

**Outputs**:
- `self.detector_profile` populated
- Fiber-specific integration time factor stored (0.5x for 200µm = 2× faster)

**Logs**:
```
✅ Detector Profile Loaded:
   Manufacturer: Ocean Optics
   Model: Flame-T (S/N: FLMT09788)
   Pixels: 2048
   Wavelength Range: 200.0-1025.0 nm
   Max Intensity: 65535 counts
   Target Signal: 40000 ± 10000 counts
   SPR Range: 500-900 nm
```

**State Reset** (if `use_previous_data=False`):
- Clears all legacy calibration data
- Ensures fresh measurement without contamination

---

### **STEP 1: Initial Dark Noise Measurement** 🌑
```python
# CRITICAL: Measure BEFORE any LED activation!
measure_dark_noise()
```

**Purpose**: Baseline noise measurement with ZERO LED contamination
**Why First**: LEDs have phosphor afterglow that contaminates subsequent measurements
**What It Does**:
- Sets temporary integration time (32ms safe default)
- Ensures **all LEDs are OFF** (never activated yet)
- Measures multiple dark spectra
- Averages to get baseline dark noise
- Stores full-spectrum dark noise

**Integration Time**: 32ms (temporary, refined in Step 4)

**Outputs**:
- `state.dark_noise` - averaged dark spectrum (ROI only)
- `state.full_spectrum_dark_noise` - full detector dark spectrum
- Typical values: 2000-3000 counts (detector baseline)

**Logs**:
```
STEP 1: Dark Noise Measurement (FIRST - No LED contamination)
✅ Initial dark noise captured with ZERO LED contamination
```

**Critical Notes**:
- ⚠️ Must run BEFORE any LED activation
- ⚠️ LED phosphor afterglow can contaminate this measurement
- ⚠️ Integration time not yet optimized (uses safe default)

---

### **STEP 2: Wavelength Range Calibration** 🌈
```python
calibrate_wavelength_range()
```

**Purpose**: Determine optimal spectral region for SPR measurements
**What It Does**:
1. Activates each LED channel sequentially
2. Measures spectral response across full detector
3. Identifies wavelength range with sufficient signal
4. Sets wavelength bounds for SPR analysis (e.g., 500-900nm)
5. Returns preliminary integration time estimate

**Process**:
- Tests all 4 channels (A, B, C, D)
- Uses detector profile's SPR range (500-900nm default)
- Finds pixel indices corresponding to wavelength bounds
- Calculates preliminary integration time (will be refined in Step 4)

**Outputs**:
- `state.wave_min_index` - Start pixel for SPR analysis
- `state.wave_max_index` - End pixel for SPR analysis
- `integration_step` - Preliminary integration time estimate
- Wavelength-to-pixel mapping

**Logs**:
```
Step 2: Wavelength range calibration
✅ Wavelength range: 500.0-900.0 nm (pixels 512-1536)
```

---

### **STEP 3: Auto-Polarization (Optional)** 🔄
```python
if auto_polarize:
    auto_polarize_callback()
```

**Purpose**: Automatically align polarizer to S-mode (perpendicular)
**What It Does**:
- If enabled, runs polarizer auto-alignment procedure
- Uses callback to GUI/hardware control
- Ensures consistent polarizer position for calibration

**Integration**: GUI-controlled, optional step
**Status**: Can be triggered by user or auto-enabled

**Note**: Typically disabled for manual calibration workflows

---

### **STEP 4: Integration Time Optimization** ⏱️
```python
calibrate_integration_time(ch_list, integration_step)
```

**Purpose**: Find optimal integration time for each LED channel
**What It Does**:
1. Tests each channel (A, B, C, D) individually
2. Adjusts integration time to achieve target signal level
3. Target: **40,000 ± 10,000 counts** (Flame-T default)
4. Avoids saturation (max 65,535 counts)
5. Ensures sufficient SNR for reliable SPR measurements

**Algorithm**:
- Binary search with adaptive steps
- Tests integration times: 5ms to max_integration_time
- Measures signal in SPR wavelength range
- Adjusts until target reached or max iterations
- Applies fiber-specific factor (0.5× for 200µm fiber)

**Outputs**:
- `state.integration` - Optimized integration time (seconds)
- Typical values: 10-80ms depending on LED brightness
- Channel-specific optimal integration times logged

**Logs**:
```
Step 4: Integration time calibration for channels ['a', 'b', 'c', 'd']
Channel A: 50ms → 38,500 counts ✅
Channel B: 55ms → 41,200 counts ✅
Channel C: 45ms → 39,800 counts ✅
Channel D: 40ms → 42,000 counts ✅
✅ Final integration time: 55ms (uses max across channels)
```

**Critical**: Uses the **maximum** integration time across all channels to ensure all channels are properly exposed

---

### **STEP 5: Final Dark Noise Re-Measurement** 🌑
```python
measure_dark_noise()  # With optimized integration time
```

**Purpose**: Re-measure dark noise with optimized integration time
**Why Re-measure**: Integration time changed in Step 4, need updated baseline
**What It Does**:
- Uses final optimized integration time from Step 4
- Re-measures dark noise with proper exposure
- Updates baseline for final calibration
- Ensures dark correction matches measurement conditions

**Integration Time**: Optimized value from Step 4 (e.g., 55ms)

**Outputs**:
- Updated `state.dark_noise` with correct integration time
- Updated `state.full_spectrum_dark_noise`

**Logs**:
```
STEP 5: Re-measuring Dark Noise (with optimized integration time)
✅ Final dark noise captured with optimized integration time (55ms)
```

**Difference from Step 1**:
- **Step 1**: Quick measurement with 32ms default (no LED contamination)
- **Step 5**: Final measurement with optimized integration (e.g., 55ms)

---

### **STEP 6: LED Intensity Calibration (S-mode Adaptive)** 💡
```python
for ch in ch_list:
    calibrate_led_s_mode_adaptive(ch)
```

**Purpose**: Calibrate each LED to achieve consistent reference signal in S-mode
**What It Does**:
1. For each channel (A, B, C, D):
   - Activates LED in S-mode (perpendicular polarization)
   - Measures signal with current LED intensity
   - Adjusts LED intensity to reach target signal
   - Target: **40,000 ± 5,000 counts** in reference region
2. Uses adaptive algorithm:
   - Binary search for optimal LED intensity (0-255 PWM)
   - Avoids saturation
   - Ensures sufficient signal for reliable SPR
3. Stores LED intensity for each channel

**Algorithm Details**:
- Tests LED intensities: 0-204 (4LED PCB) or 0-255 (8LED PCB)
- Measures reference signal in SPR wavelength range
- Adjusts intensity until target achieved
- Falls back to max intensity if target unreachable
- Logs achieved signal level for each channel

**Outputs**:
- `state.ref_intensity[ch]` - LED intensity for each channel (0-255)
- Typical values:
  - Channel D (brightest): 120-150
  - Channel A/B: 180-204
  - Channel C: 160-190

**Logs**:
```
Step 6: LED intensity calibration (S-mode adaptive)
Channel A: Intensity 185 → 39,800 counts ✅
Channel B: Intensity 198 → 40,500 counts ✅
Channel C: Intensity 165 → 41,200 counts ✅
Channel D: Intensity 135 → 39,500 counts ✅
✅ S-mode LED calibration complete
```

**Critical Notes**:
- ⚠️ Uses **NEW** HAL method `set_led_intensity()` (just fixed!)
- ⚠️ Ensures consistent signal across all 4 channels
- ⚠️ Foundation for repeatable SPR measurements

---

### **STEP 7A: Reference Signal Measurement (S-mode)** 📈
```python
measure_reference_signals(ch_list)
```

**Purpose**: Capture S-mode reference signals with calibrated LED intensities
**What It Does**:
1. For each channel with calibrated intensity:
   - Activates LED in S-mode
   - Sets LED to calibrated intensity from Step 6
   - Measures reference spectrum
   - Subtracts dark noise
   - Stores reference signal
2. These references are used for:
   - Baseline subtraction in SPR measurements
   - Transmittance calculations: T = (sample - dark) / (ref - dark)
   - Quality validation

**Outputs**:
- `state.ref_sig[ch]` - Reference spectrum for each channel
- Stored in SPR wavelength range (500-900nm)
- Typical values: 35,000-45,000 counts after dark subtraction

**Logs**:
```
Step 7: Reference signal measurement (S-mode)
✅ Reference signals captured for all channels
```

---

### **STEP 7B: Switch to P-mode** 🔄
```python
ctrl.set_mode(mode="p")
time.sleep(0.4)  # Polarizer movement settling time
```

**Purpose**: Switch from S-mode (perpendicular) to P-mode (parallel)
**What It Does**:
- Commands servo to rotate polarizer to P position
- Waits 400ms for mechanical movement
- P-mode needed for SPR measurements (parallel polarization)

**Physical Movement**: Servo rotates from S position (~10°) to P position (~100°)

**Logs**:
```
Step 7: Switching to P-mode
✅ Polarizer moved to P position
```

---

### **STEP 8: LED Intensity Calibration (P-mode S-based)** 💡
```python
calibrate_led_p_mode_s_based(ch_list)
```

**Purpose**: Optimize LED intensities for P-mode measurements
**What It Does**:
1. Uses S-mode calibration as starting point
2. For each channel:
   - Tests signal in P-mode with S-mode intensity
   - Adjusts if needed (P-mode typically needs ~1.2× S-mode intensity)
   - Validates signal level meets target
   - Stores P-mode LED intensity
3. Ensures consistent signal quality in P-mode

**Algorithm**:
- Starts with S-mode intensity × 1.2 (P-mode boost factor)
- Measures P-mode signal
- Adjusts if outside target range
- Stores final P-mode LED intensity

**Outputs**:
- `state.leds_calibrated[ch]` - P-mode LED intensity (0-255)
- `state.p_pol_intensity[ch]` - P-mode intensity values
- Typical values: 1.1-1.3× S-mode intensity

**Logs**:
```
Step 8: LED intensity calibration (P-mode S-based)
Channel A: S-mode 185 → P-mode 215 (1.16×) ✅
Channel B: S-mode 198 → P-mode 204 (1.03×) ✅
Channel C: S-mode 165 → P-mode 195 (1.18×) ✅
Channel D: S-mode 135 → P-mode 160 (1.19×) ✅
✅ P-mode LED calibration complete
```

**Why P-mode needs higher intensity**:
- Polarizer absorption losses
- Parallel polarization has different optical properties
- SPR measurements require consistent signal in P-mode

---

### **STEP 9: Calibration Validation** ✅
```python
validate_calibration()
```

**Purpose**: Verify calibration quality and identify failed channels
**What It Does**:
1. **Signal Level Check**:
   - Verifies all reference signals are > 10,000 counts
   - Ensures no saturation (< max_intensity)
   - Checks signal consistency across channels

2. **LED Intensity Check**:
   - Validates all LED intensities are > 0
   - Confirms no channels failed to calibrate

3. **Integration Time Check**:
   - Verifies integration time is reasonable (5-200ms)
   - Checks against detector max

4. **Dark Noise Check**:
   - Ensures dark noise was measured
   - Validates dark array size matches ROI

5. **Wavelength Range Check**:
   - Confirms wavelength bounds are set
   - Validates SPR range is within detector limits

**Outputs**:
- `success` (bool) - Overall calibration success
- `error_channels` (str) - Comma-separated list of failed channels (if any)
- Validation report logged

**Logs**:
```
Step 9: Validation
✅ Channel A: 39,800 counts, LED 185 (S), 215 (P)
✅ Channel B: 40,500 counts, LED 198 (S), 204 (P)
✅ Channel C: 41,200 counts, LED 165 (S), 195 (P)
✅ Channel D: 39,500 counts, LED 135 (S), 160 (P)
✅ Integration time: 55ms
✅ Wavelength range: 500-900nm (pixels 512-1536)
✅ Dark noise: Valid (2048 pixels)

✅✅✅ CALIBRATION SUCCESSFUL ✅✅✅
```

**Failure Cases**:
```
❌ Channel B: Signal too low (8,500 counts < 10,000)
❌ Channel C: LED calibration failed (intensity = 0)
⚠️ CALIBRATION FAILED: Channels B,C
```

---

### **Post-Validation: Hardware Cleanup** 🧹
```python
_safe_hardware_cleanup()
```

**Purpose**: Ensure hardware is in safe state after calibration
**What It Does**:
- Turns off all LEDs (`ctrl.emergency_shutdown()`)
- Resets polarizer to neutral position (optional)
- Clears any hardware buffers
- Ensures no LEDs left on (prevents heat/wear)

**Always Runs**: Even if calibration fails or is interrupted

---

### **Post-Validation: Auto-Save** 💾
```python
if calibration_success and auto_save:
    save_profile(f"auto_save_{timestamp}", device_type)
```

**Purpose**: Automatically save successful calibration
**What It Does**:
- Generates timestamped filename: `auto_save_20251011_220530`
- Saves complete calibration state to JSON
- Stores in `calibration_profiles/` directory
- Includes:
  - All LED intensities (S-mode and P-mode)
  - Integration time
  - Wavelength range
  - Dark noise
  - Reference signals
  - Device metadata (serial numbers, fiber type, LED model)

**File Location**: `config/calibration_profiles/auto_save_YYYYMMDD_HHMMSS.json`

**Logs**:
```
💾 Auto-saving calibration data...
✅ Calibration saved as: auto_save_20251011_220530
```

---

## Summary Timeline

```
STEP 0: Detector Profile Loading                   [~1 second]
        ↓
STEP 1: Dark Noise (32ms temp integration)         [~2-3 seconds, 10 measurements]
        ↓
STEP 2: Wavelength Range Calibration               [~5-8 seconds, 4 channels tested]
        ↓
STEP 3: Auto-Polarize (optional)                   [~2-5 seconds if enabled]
        ↓
STEP 4: Integration Time Optimization              [~15-25 seconds, binary search × 4 channels]
        ↓
STEP 5: Dark Noise Re-measurement                  [~2-3 seconds with optimized integration]
        ↓
STEP 6: LED Intensity Cal (S-mode)                 [~20-30 seconds, adaptive × 4 channels]
        ↓
STEP 7A: Reference Signal Capture (S-mode)         [~3-5 seconds]
        ↓
STEP 7B: Switch to P-mode                          [~0.5 seconds, servo movement]
        ↓
STEP 8: LED Intensity Cal (P-mode S-based)         [~15-20 seconds]
        ↓
STEP 9: Validation                                 [~1-2 seconds]
        ↓
Cleanup & Auto-save                                [~1 second]

TOTAL TIME: ~70-100 seconds (~1.5 minutes typical)
```

---

## Critical Data Flow

### Inputs (from Hardware/Config)
- Spectrometer object (USB connection)
- Controller object (PicoP4SPR)
- Device config (fiber diameter, LED model, serial numbers)
- Detector profile (auto-detected or legacy defaults)

### Outputs (to CalibrationState)
```python
state.dark_noise              # Dark baseline (ROI)
state.full_spectrum_dark_noise  # Full detector dark
state.integration             # Optimized integration time (seconds)
state.wave_min_index          # SPR wavelength range start (pixel)
state.wave_max_index          # SPR wavelength range end (pixel)
state.ref_intensity[ch]       # S-mode LED intensities (0-255)
state.leds_calibrated[ch]     # P-mode LED intensities (0-255)
state.ref_sig[ch]             # S-mode reference spectra
state.num_scans               # Number of scans for averaging
state.is_calibrated           # True if validation passed
```

### Persisted (to disk)
- JSON calibration profile (timestamped)
- Calibration history log (JSONL + CSV)
- Device config updated with calibration flags

---

## Known Issues & Future Work

### Current Issues
1. **LED Afterglow Not Corrected**:
   - Dark noise in Step 1 is clean (no LEDs activated yet) ✅
   - But subsequent steps have channel-to-channel contamination
   - **Solution**: Implement optical system calibration (τ lookup tables)

2. **Integration Time Not Channel-Specific**:
   - Uses single integration time (max across channels)
   - Could be optimized per-channel for 2× speed improvement
   - **Trade-off**: Complexity vs speed

3. **No Intensity-Dependent Calibration**:
   - Assumes LED intensity doesn't affect decay constant τ
   - Validated theoretically but not experimentally
   - **Status**: HAL now supports `set_led_intensity()` (just fixed!)

### Future Enhancements

### ✅ **DECISION: Optical System Calibration Architecture**

**NOT Step 10** - Separate OEM Tool (Maintenance Procedure)

**Architecture**:
- **Separate procedure**: NOT part of main 9-step calibration
- **Standalone script**: `optical_system_calibration.py` (OEM tools)
- **Infrequent**: Run once per ~1000 hours of operation (to be defined)
- **One-time characterization**: Generates τ(integration_time) lookup tables
- **Correction always active**: Load existing model during measurements
- **No re-calibration**: Just apply correction using stored τ tables

**Workflow**:
```
Main Calibration (9 steps, ~1.5 min)
  ↓ (every startup or hardware change)
SPR Measurements with Correction
  ↓ (uses existing optical calibration file)
  ↓ (corrects afterglow using τ tables)
  ↓
[After ~1000 hours operation]
  ↓
Optical System Calibration (OEM tool, ~2-3 min)
  ↓ (generates new τ tables, saves to file)
Resume measurements
```

**Rationale**:
1. **Different timescales**:
   - Main calibration: Frequent (~daily, when hardware changes)
   - Optical calibration: Rare (~1000 hours, LED aging/wear)
2. **Different purpose**:
   - Main calibration: LED intensity, integration time, baselines
   - Optical calibration: LED phosphor decay characterization
3. **Correction is passive**: Once τ tables exist, just load + apply
4. **OEM-facing**: Maintenance procedure, not routine workflow
5. **No dependency**: Can run independently, doesn't affect main calibration

**Files Structure**:
```
config/
  optical_calibration/
    system_FLMT09788_20251011_210859.json  # τ tables, one per system
device_config.json                          # Links to optical calibration file
```

---

2. **Parallel Channel Calibration**:
   - Step 6 & 8 could be parallelized (if hardware supports)
   - Reduce calibration time by ~30%

3. **Adaptive Validation Thresholds**:
   - Use detector-specific target signals from profile
   - Currently hardcoded for Flame-T

4. **Real-time Progress Visualization**:
   - Live spectrum display during calibration
   - Signal quality indicators
   - ETA estimation

---

## Related Files

- **`utils/spr_calibrator.py`** - Calibration implementation (2763 lines)
- **`utils/spr_state_machine.py`** - State machine orchestration
- **`utils/detector_manager.py`** - Detector profile management
- **`utils/spr_data_acquisition.py`** - Uses calibration data for measurements
- **`config/device_config.json`** - Persisted device configuration
- **`config/calibration_profiles/*.json`** - Saved calibration profiles

---

**Last Updated**: October 11, 2025
**Next Review**: After optical system calibration integration (Step 10)
