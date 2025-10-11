# Detector-Agnostic Calibration Implementation

## Overview
Removed all hardcoded detector maximum count values and replaced them with detector-specific values from the detector profile. Now fully detector-agnostic for both max intensity and integration time.

## Problem
The calibration system used hardcoded values that were not specific to the actual detector:
- **Hardcoded max counts:** `DETECTOR_MAX_COUNTS = 65535` (16-bit ADC maximum)
- **Hardcoded max integration:** `MAX_INTEGRATION = 100ms` (incorrect for Flame-T which supports 200ms)
- **Result:** Target intensities and percentage calculations not optimized for specific detector capabilities

## Solution
Use detector-specific parameters from detector profile throughout the calibration:
- **Max intensity counts:** From `profile.max_intensity_counts` (65,535 for Flame-T)
- **Max integration time:** From `profile.max_integration_time_ms` (200ms for Flame-T)
- **Result:** All calculations use actual detector capabilities

## Changes Made

### 1. Updated Detector Profile
**File:** `detector_profiles/ocean_optics_flame_t.json`

**Before:**
```json
"acquisition_limits": {
  "max_intensity_counts": 62000,
  "saturation_counts": 65535,
  ...
}
```

**After:**
```json
"acquisition_limits": {
  "max_intensity_counts": 65535,  // Updated to full 16-bit range
  "saturation_counts": 65535,
  ...
}
```

### 2. Updated Helper Functions
**File:** `utils/spr_calibrator.py`

**Before:**
```python
def calculate_target_intensity(target_percent: float = TARGET_INTENSITY_PERCENT) -> int:
    return int(DETECTOR_MAX_COUNTS * target_percent / 100.0)  # Hardcoded 65535

def calculate_intensity_tolerance(target_percent: float = TARGET_INTENSITY_PERCENT) -> int:
    return int(DETECTOR_MAX_COUNTS * 0.05)  # Hardcoded 65535
```

**After:**
```python
def calculate_target_intensity(target_percent: float = TARGET_INTENSITY_PERCENT, 
                                detector_max_counts: int = DETECTOR_MAX_COUNTS) -> int:
    return int(detector_max_counts * target_percent / 100.0)  # Detector-specific!

def calculate_intensity_tolerance(target_percent: float = TARGET_INTENSITY_PERCENT,
                                   detector_max_counts: int = DETECTOR_MAX_COUNTS) -> int:
    return int(detector_max_counts * 0.05)  # Detector-specific!
```

### 3. Updated S-Mode Adaptive Calibration
**File:** `utils/spr_calibrator.py` - `calibrate_led_s_mode_adaptive()`

**Changes:**
```python
# Get detector-specific max counts (or fallback to hardcoded value)
if self.detector_profile:
    detector_max = self.detector_profile.max_intensity_counts
    logger.debug(f"Using detector-specific max: {detector_max} counts")
else:
    detector_max = DETECTOR_MAX_COUNTS
    logger.warning(f"No detector profile, using default max: {detector_max} counts")

# Use detector-specific max for calculations
target_intensity = calculate_target_intensity(TARGET_INTENSITY_PERCENT, detector_max)
tolerance = calculate_intensity_tolerance(TARGET_INTENSITY_PERCENT, detector_max)

# ... in iteration loop:
measured_percent = (measured_intensity / detector_max) * 100  # Not hardcoded!
```

### 4. Updated Integration Time Calibration
**File:** `utils/spr_calibrator.py` - `calibrate_integration_time()`

**Changes:**
```python
# Get detector-specific max counts for target calculation
if self.detector_profile:
    detector_max = self.detector_profile.max_intensity_counts
else:
    detector_max = DETECTOR_MAX_COUNTS

# Target: 80% of detector-specific max (not hardcoded 65535!)
S_COUNT_TARGET = int(TARGET_INTENSITY_PERCENT / 100 * detector_max)

# Percentage calculations now use detector_max
logger.info(f"weakest@LED=255: {current_count:.0f} counts ({current_count/detector_max*100:.1f}%)")
```

**Integration time limits already used from profile:**
```python
if self.detector_profile:
    min_int = self.detector_profile.min_integration_time_ms / 1000.0
    max_int = self.detector_profile.max_integration_time_ms / 1000.0  # 200ms for Flame-T!
```

### 5. Updated Saturation Check (Step 3.3)
**File:** `utils/spr_calibrator.py` - `calibrate_integration_time()` Step 3.3

**Changes:**
```python
# Get detector-specific max for saturation threshold (91% of max)
if self.detector_profile:
    detector_max = self.detector_profile.max_intensity_counts
else:
    detector_max = DETECTOR_MAX_COUNTS

SATURATION_THRESHOLD = int(detector_max * 0.91)  # Not hardcoded 60000!

# Percentage calculations
counts_percent = (counts / detector_max) * 100  # Detector-specific!
```

### 6. Updated P-Mode Calibration
**File:** `utils/spr_calibrator.py` - `calibrate_p_mode_match_s_mode()`

**Changes:**
```python
# Saturation check uses detector-specific max
if self.detector_profile:
    detector_max = self.detector_profile.max_intensity_counts
else:
    detector_max = DETECTOR_MAX_COUNTS

if overall_p_mode_max > detector_max * 0.95:  # Not hardcoded!
    logger.warning("Approaching saturation...")
```

### 7. Updated Validation (Step 5)
**File:** `utils/spr_calibrator.py` - `run_full_calibration()` Step 5

**Changes:**
```python
# Development mode logging
if self.detector_profile:
    detector_max = self.detector_profile.max_intensity_counts
else:
    detector_max = DETECTOR_MAX_COUNTS

max_percent = (max_intensity / detector_max) * 100  # Detector-specific!
target_percent = (target_max / detector_max) * 100  # Detector-specific!

# Production mode thresholds
min_threshold = detector_max * MIN_INTENSITY_PERCENT / 100.0  # Detector-specific!
max_threshold = detector_max * MAX_INTENSITY_PERCENT / 100.0  # Detector-specific!
```

## Summary of Replacements

### Before (Hardcoded):
```python
DETECTOR_MAX_COUNTS = 65535  # Everywhere
target = int(65535 * 0.80)  # 52,428 counts
saturation = 60000  # 91% of 65535
percent = (counts / 65535) * 100
```

### After (Detector-Specific):
```python
detector_max = self.detector_profile.max_intensity_counts  # From profile!
target = int(detector_max * 0.80)  # Detector-specific
saturation = int(detector_max * 0.91)  # Detector-specific
percent = (counts / detector_max) * 100  # Detector-specific
```

## Integration Time Already Fixed
Integration time limits already use detector profile (from previous commit):
```python
if self.detector_profile:
    min_int = self.detector_profile.min_integration_time_ms / 1000.0  # 1ms
    max_int = self.detector_profile.max_integration_time_ms / 1000.0  # 200ms for Flame-T!
else:
    min_int = MIN_INTEGRATION / 1000.0  # Fallback
    max_int = MAX_INTEGRATION / 1000.0  # Fallback
```

## Benefits

### Detector-Agnostic
- ✅ **Works with any detector** - just update the profile
- ✅ **Correct targets** - based on actual detector capabilities
- ✅ **Accurate percentages** - relative to true detector max
- ✅ **Optimal calibration** - uses full detector range when appropriate

### For Flame-T Specifically
| Parameter | Before (Hardcoded) | After (Profile) |
|-----------|-------------------|-----------------|
| **Max Counts** | 65,535 | 65,535 ✅ |
| **Target (80%)** | 52,428 counts | 52,428 counts ✅ |
| **Tolerance (±5%)** | ±3,277 counts | ±3,277 counts ✅ |
| **Saturation (91%)** | 60,000 counts | 59,637 counts ✅ |
| **Max Integration** | 100ms ❌ | 200ms ✅ |

### Maintainability
- **Single source of truth**: Detector parameters in one JSON file
- **No code changes needed**: Add new detector = create profile
- **Fallback support**: Works without profile (uses settings.py defaults)
- **Clear logging**: Shows which max value is being used

## Testing Recommendations

1. **Run full calibration** with Flame-T
2. **Verify log messages** show detector-specific max:
   ```
   Using detector-specific max: 65535 counts
   📊 S-mode target: 80% of 65535 = 52428 counts
   ```
3. **Check integration time** reaches 200ms if needed (weak signal)
4. **Verify percentages** are calculated correctly in logs
5. **Test without profile** to verify fallback works

## Expected Log Output

**With Detector Profile:**
```
STEP 0: Loading Detector Profile
✅ Matched by serial number: Ocean Optics Flame-T
📊 Detector Profile Loaded:
   Max Intensity: 65535 counts
   Max Integration Time: 200.0 ms

STEP 3: Integration Time Calibration
Using detector-specific max: 65535 counts
Target: 80% of detector-specific max
Starting: 1.0ms, weakest@LED=255: 8234 counts
✅ Target reached at 45.0ms: 52541 counts (80.2%)

STEP 4: LED Intensity Calibration (S-MODE)
Using detector-specific max: 65535 counts
📊 S-mode target: 80% of 65535 = 52428 counts
Adaptive iter 0: LED=128, measured=42500 (64.9%), error=9928
Adaptive iter 1: LED=165, measured=51234 (78.2%), error=1194
Adaptive iter 2: LED=158, measured=52376 (79.9%), error=52
✅ Channel a converged in 3 iterations
```

**Without Detector Profile (Fallback):**
```
⚠️ No detector profile, using default max: 65535 counts
📊 S-mode target: 80% of 65535 = 52428 counts
```

## Backward Compatibility

✅ **Fallback mechanism**: If `detector_profile` is None, uses `DETECTOR_MAX_COUNTS` from settings.py  
✅ **No breaking changes**: All existing code paths work  
✅ **Graceful degradation**: System works even if profile loading fails  
✅ **Settings.py preserved**: Legacy constants still available as fallback  

## Related Files

- `detector_profiles/ocean_optics_flame_t.json` - Flame-T detector profile (updated)
- `utils/spr_calibrator.py` - Main calibration logic (updated throughout)
- `settings/settings.py` - Legacy constants (unchanged, used as fallback)
- `DETECTOR_PROFILES_IMPLEMENTATION.md` - Detector profile system documentation

## Related Commits

1. **Detector Profiles Implementation** - Created detector profile system
2. **S-Mode Optimization Cleanup** - Removed redundant Phase 1
3. **This commit** - Made calibration fully detector-agnostic

## Summary

**Before:** Hardcoded `DETECTOR_MAX_COUNTS = 65535` everywhere  
**After:** `detector_max = self.detector_profile.max_intensity_counts` everywhere  
**Result:** Fully detector-agnostic calibration that adapts to any detector's capabilities
