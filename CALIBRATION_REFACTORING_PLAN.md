# Calibration Code Refactoring Plan

**Date**: November 21, 2025
**Goal**: Clean up calibration code to align with UI workflow and device architecture

## Issues Found

### 1. **Excessive use of `deepcopy()`**
- **Problem**: `deepcopy()` is used for simple primitive types (int, float) where it's unnecessary
- **Locations**:
  - Line 80, 81: `deepcopy(MIN_INTEGRATION)`, `deepcopy(MAX_INTEGRATION)`
  - Line 134, 176, 278, 289, 342, 461: Various deepcopy calls for integers
- **Fix**: Remove deepcopy for primitive types - they're immutable in Python
- **Impact**: Slight performance improvement, cleaner code

### 2. **Magic Numbers for Sleep Delays**
- **Problem**: Hardcoded `time.sleep(0.4)` and `time.sleep(0.5)` appear multiple times
- **Locations**: Lines 89, 266, 431, 675
- **Fix**: Create constants for mode switching delays
- **Reason**: These are settling times for servo/polarizer rotation

### 3. **Duplicate Adjustment Logic**
- **Problem**: `calibrate_led_channel()` and `calibrate_p_mode_leds()` have nearly identical coarse/medium/fine adjustment loops
- **Locations**:
  - Lines 193-238 in `calibrate_led_channel()`
  - Lines 293-340 in `calibrate_p_mode_leds()`
- **Fix**: Extract common adjustment algorithm to helper function
- **Benefit**: DRY principle, easier to maintain

### 4. **Magic Number `fifty = 50`**
- **Problem**: Variable named `fifty` used as threshold for adjusting scan counts
- **Locations**: Lines 372, 438
- **Fix**: Replace with named constant `INTEGRATION_THRESHOLD_MS = 50`
- **Reason**: More descriptive, shows this is integration time threshold

### 5. **Inconsistent Error Handling**
- **Problem**: Some functions check `intensity_data is None`, others don't
- **Fix**: Consistent error handling pattern throughout
- **Add**: Specific error types for different failure modes

### 6. **Step Numbers in Debug Logs**
- **Problem**: "Step 3/6", "Step 4/6", "Step 5/6" hardcoded in debug logs
- **Locations**: Lines 692, 702, 735
- **Issue**: If steps change, numbers must be manually updated
- **Fix**: Remove step numbers, use descriptive messages only

## Refactoring Implementation

### Phase 1: Remove Unnecessary deepcopy()
```python
# BEFORE
integration = deepcopy(MIN_INTEGRATION)
max_int = deepcopy(MAX_INTEGRATION)

# AFTER
integration = MIN_INTEGRATION
max_int = MAX_INTEGRATION
```

### Phase 2: Add Mode Switching Constants
```python
# Add to settings.py or as module constants
MODE_SWITCH_DELAY = 0.5  # seconds - settling time for S/P mode switching
P_MODE_SWITCH_DELAY = 0.4  # seconds - slightly faster for P-mode
```

### Phase 3: Extract Common LED Adjustment Logic
```python
def _adjust_led_intensity(
    usb: USB4000,
    ctrl: ControllerBase,
    ch: str,
    initial_intensity: int,
    target_counts: float,
    max_intensity: int = P_LED_MAX,
    stop_flag=None,
) -> int:
    """Common LED intensity adjustment using coarse/medium/fine steps.

    Args:
        usb: Spectrometer instance
        ctrl: Controller instance
        ch: Channel to adjust
        initial_intensity: Starting LED intensity
        target_counts: Target detector counts
        max_intensity: Maximum allowed intensity
        stop_flag: Cancellation flag

    Returns:
        Final calibrated intensity value
    """
    # Implementation with coarse(20), medium(5), fine(1) adjustments
```

### Phase 4: Create Descriptive Constants
```python
# LED adjustment step sizes
COARSE_ADJUST_STEP = 20   # Initial large adjustments
MEDIUM_ADJUST_STEP = 5    # Medium refinement
FINE_ADJUST_STEP = 1      # Final precision adjustment

# Integration time thresholds
INTEGRATION_THRESHOLD_MS = 50  # Threshold for adjusting scan averaging
```

### Phase 5: Consolidate Error Types
```python
class CalibrationError(Exception):
    """Base exception for calibration failures."""
    pass

class SpectrometerReadError(CalibrationError):
    """Spectrometer failed to read intensity."""
    pass

class CalibrationTimeoutError(CalibrationError):
    """Calibration exceeded time limit."""
    pass
```

## Alignment with Architecture

### Current Device Architecture:
```
Device Core Functions (common to all devices):
├── Spectroscopy Hardware
│   ├── Detector (USB4000/Flame-T)
│   ├── LED Control (4 channels)
│   ├── Polarizer (S/P mode switching)
│   └── Integration Time Control
│
├── Calibration System
│   ├── Integration Time Optimization
│   ├── LED Intensity Calibration
│   ├── Dark Noise Measurement
│   └── Reference Signal Capture
│
├── Settings & Parameters
│   ├── LED Delays
│   ├── Integration Limits
│   ├── Scan Averaging
│   └── Wavelength Range
│
└── Graphics Display
    ├── Timeline Plots
    ├── Transmission Spectra
    ├── Raw Data Visualization
    └── Quality Metrics

Device-Specific Functions:
└── Pumps (P4SPR, EZSPR only)
```

### Calibration Module Organization:
```
led_calibration.py
├── Core Calibration Functions
│   ├── calibrate_integration_time()  # Step 1: Find optimal integration
│   ├── calibrate_led_channel()       # Step 2: S-mode LED intensity
│   ├── measure_dark_noise()          # Step 3: Background measurement
│   ├── measure_reference_signals()   # Step 4: S-ref capture
│   ├── calibrate_p_mode_leds()       # Step 5: P-mode LED intensity
│   └── verify_calibration()          # Step 6: Validation
│
├── Quality Control
│   └── validate_s_ref_quality()      # Optical QC checks
│
├── Helper Functions (NEW - after refactoring)
│   ├── _adjust_led_intensity()       # Common adjustment logic
│   ├── _read_intensity_with_retry()  # Robust reading with retries
│   └── _calculate_scan_count()       # Determine scans based on integration
│
└── Data Structures
    └── LEDCalibrationResult          # Complete calibration results
```

## Benefits of Refactoring

1. **Cleaner Code**: Remove 20+ unnecessary `deepcopy()` calls
2. **Maintainability**: Extract duplicate logic to single function
3. **Readability**: Named constants instead of magic numbers
4. **Alignment**: Matches UI workflow (6-step calibration process)
5. **Consistency**: Uniform error handling throughout
6. **Performance**: Slight improvement from removing unnecessary deep copies
7. **Extensibility**: Easier to add new calibration steps or modify existing ones

## No Changes Needed

✅ **Calibration Flow**: Current 6-step sequence is optimal and matches UI
✅ **QC Validation**: `validate_s_ref_quality()` is well-structured
✅ **Result Structure**: `LEDCalibrationResult` class is comprehensive
✅ **HAL Integration**: Detector properties correctly abstracted
✅ **Device Type Handling**: Proper channel list selection (EZ vs P4)

## Implementation Priority

1. **HIGH**: Remove unnecessary `deepcopy()` calls (immediate performance gain)
2. **HIGH**: Add named constants for magic numbers (clarity)
3. **MEDIUM**: Extract common LED adjustment logic (DRY principle)
4. **MEDIUM**: Consolidate error handling (robustness)
5. **LOW**: Remove hardcoded step numbers from logs (cosmetic)
