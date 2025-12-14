# Phase 1 Implementation: Production Multi-Channel Afterglow Correction

**Status**: 🚀 In Progress
**Date**: October 11, 2025
**Priority**: HIGHEST (2× speed improvement for production measurements)

---

## Implementation Overview

### **Goal**: Enable 2 Hz multi-channel acquisition with afterglow correction

**Current State**:
- 4-channel scan: ~700ms (with 5ms delays between channels to avoid afterglow)
- Acquisition frequency: ~1.4 Hz max
- No afterglow correction

**Target State**:
- 4-channel scan: ~300ms (with correction, no extra delays)
- Acquisition frequency: 2 Hz+ (real-world validated)
- Afterglow correction applied automatically
- Both raw + corrected data stored

---

## Files to Create/Modify

### **1. Create: `afterglow_correction.py`** (NEW)
**Purpose**: Load optical calibration and apply correction
**Status**: ⏳ To be implemented

**Key Features**:
- Load τ(integration_time) lookup tables from optical calibration JSON
- Cubic spline interpolation for arbitrary integration times (10-80ms)
- Calculate expected afterglow: `baseline + A × exp(-delay/τ)`
- Apply correction to measurement data
- Graceful degradation if optical calibration unavailable

---

### **2. Modify: `utils/spr_data_acquisition.py`**
**Purpose**: Integrate afterglow correction into production acquisition
**Status**: ⏳ To be implemented

**Key Changes**:
```python
class SPRDataAcquisition:
    def __init__(self, ...):
        # NEW: Load optical calibration
        self.afterglow_correction = None
        if device_config.get('optical_calibration_file'):
            self.afterglow_correction = AfterglowCorrection(
                device_config['optical_calibration_file']
            )

        # NEW: Track previous channel for correction
        self._previous_channel = None

        # NEW: Enable/disable flag
        self.afterglow_correction_enabled = device_config.get(
            'afterglow_correction_enabled', True
        )

    def _read_channel_data(self, ch: str) -> float:
        # Existing code: activate LED, measure, average...

        # NEW: Apply afterglow correction
        if self.afterglow_correction and self._previous_channel:
            corrected = self._apply_afterglow_correction(
                averaged_intensity, ch
            )
        else:
            corrected = averaged_intensity

        # Store both raw + corrected
        self.int_data[ch] = averaged_intensity  # Raw
        corrected_intensity = corrected  # Use for further processing

        # Update previous channel
        self._previous_channel = ch

        return fit_lambda  # Continue normal processing
```

---

### **3. Modify: `config/device_config.json`**
**Purpose**: Link to optical calibration file
**Status**: ⏳ To be implemented

**New Fields**:
```json
{
  "optical_calibration_file": "optical_calibration/system_FLMT09788_20251011_210859.json",
  "afterglow_correction_enabled": true,
  "afterglow_correction_delay_ms": 5.0
}
```

---

## Implementation Steps

### **Step 1: Create `afterglow_correction.py`** ✅ NEXT

**Module Structure**:
```python
"""Afterglow Correction Module

Loads optical calibration τ tables and applies correction to measurements.
This is a passive module - it does NOT run calibration, only loads and applies.
"""

from pathlib import Path
import json
import numpy as np
from scipy.interpolate import CubicSpline
from utils.logger import logger


class AfterglowCorrection:
    """Apply LED phosphor afterglow correction using optical calibration data."""

    def __init__(self, calibration_file: str | Path):
        """Load optical calibration from JSON file.

        Args:
            calibration_file: Path to optical calibration JSON
                             (e.g., 'optical_calibration/system_FLMT09788_20251011.json')

        Raises:
            FileNotFoundError: If calibration file doesn't exist
            ValueError: If calibration data is invalid
        """
        self.calibration_file = Path(calibration_file)
        self.calibration_data = self._load_calibration()
        self._build_interpolators()

        logger.info(f"✅ Optical calibration loaded: {self.calibration_file.name}")
        logger.info(f"   Channels: {list(self.tau_interpolators.keys())}")
        logger.info(f"   Integration time range: {self.int_time_range_ms}")

    def _load_calibration(self) -> dict:
        """Load and validate calibration JSON."""
        if not self.calibration_file.exists():
            raise FileNotFoundError(
                f"Optical calibration file not found: {self.calibration_file}"
            )

        with open(self.calibration_file, 'r') as f:
            data = json.load(f)

        # Validate structure
        if 'channel_data' not in data:
            raise ValueError("Invalid calibration file: missing 'channel_data'")

        return data

    def _build_interpolators(self):
        """Build cubic spline interpolators for τ(integration_time)."""
        self.tau_interpolators = {}
        self.amplitude_tables = {}
        self.baseline_tables = {}

        for channel, ch_data in self.calibration_data['channel_data'].items():
            # Extract arrays for interpolation
            int_times = []
            taus = []
            amplitudes = []
            baselines = []

            for data_point in ch_data['integration_time_data']:
                int_times.append(data_point['integration_time_ms'])
                taus.append(data_point['tau_ms'])
                amplitudes.append(data_point['amplitude'])
                baselines.append(data_point['baseline'])

            # Build cubic spline interpolators
            self.tau_interpolators[channel] = CubicSpline(int_times, taus)
            self.amplitude_tables[channel] = CubicSpline(int_times, amplitudes)
            self.baseline_tables[channel] = CubicSpline(int_times, baselines)

        # Store integration time range for validation
        self.int_time_range_ms = (min(int_times), max(int_times))

    def calculate_correction(
        self,
        previous_channel: str,
        integration_time_ms: float,
        delay_ms: float = 5.0
    ) -> float:
        """Calculate expected afterglow signal from previous channel.

        Args:
            previous_channel: Channel ID ('a', 'b', 'c', 'd') that was last active
            integration_time_ms: Integration time used for measurement (10-100ms)
            delay_ms: Time delay since previous LED turned off (default: 5ms)

        Returns:
            Expected afterglow signal (counts) to subtract from measurement

        Raises:
            ValueError: If channel invalid or integration time out of range
        """
        # Validate channel
        channel_lower = previous_channel.lower()
        if channel_lower not in self.tau_interpolators:
            raise ValueError(
                f"Invalid channel: {previous_channel}. "
                f"Available: {list(self.tau_interpolators.keys())}"
            )

        # Validate integration time
        min_int, max_int = self.int_time_range_ms
        if not (min_int <= integration_time_ms <= max_int):
            logger.warning(
                f"Integration time {integration_time_ms}ms outside calibrated range "
                f"[{min_int}, {max_int}]ms. Correction may be less accurate."
            )

        # Interpolate τ, amplitude, baseline for this integration time
        tau = float(self.tau_interpolators[channel_lower](integration_time_ms))
        amplitude = float(self.amplitude_tables[channel_lower](integration_time_ms))
        baseline = float(self.baseline_tables[channel_lower](integration_time_ms))

        # Calculate exponential decay: signal(t) = baseline + A × exp(-t/τ)
        correction = baseline + amplitude * np.exp(-delay_ms / tau)

        logger.debug(
            f"Afterglow correction: Ch {previous_channel} @ {integration_time_ms}ms, "
            f"delay={delay_ms}ms → τ={tau:.2f}ms, correction={correction:.1f} counts"
        )

        return correction

    def apply_correction(
        self,
        measured_signal: np.ndarray | float,
        previous_channel: str,
        integration_time_ms: float,
        delay_ms: float = 5.0
    ) -> np.ndarray | float:
        """Apply afterglow correction to measured signal.

        Args:
            measured_signal: Raw measured spectrum or single value
            previous_channel: Channel that was last active
            integration_time_ms: Integration time used (ms)
            delay_ms: Delay since previous LED off (ms)

        Returns:
            Corrected signal (same type as input)
        """
        correction = self.calculate_correction(
            previous_channel, integration_time_ms, delay_ms
        )

        # Subtract correction from signal
        if isinstance(measured_signal, np.ndarray):
            # Array: subtract uniform correction from all pixels
            corrected = measured_signal - correction
        else:
            # Scalar: direct subtraction
            corrected = measured_signal - correction

        return corrected

    def get_calibration_info(self) -> dict:
        """Get information about loaded calibration."""
        return {
            'file': str(self.calibration_file),
            'channels': list(self.tau_interpolators.keys()),
            'integration_time_range_ms': self.int_time_range_ms,
            'metadata': self.calibration_data.get('metadata', {})
        }
```

**Tests to Include**:
- Load calibration file
- Interpolate τ at non-calibrated points (30ms, 60ms)
- Calculate correction values
- Apply to spectrum array
- Handle edge cases (out of range, invalid channel)

---

### **Step 2: Integrate into `spr_data_acquisition.py`**

**Location**: `__init__` method (line ~37)

**Add after existing initialization**:
```python
# Log integration time acceleration status
if self.base_integration_time_factor < 1.0:
    logger.info(...)
else:
    logger.info(...)

# ✨ NEW: Load optical calibration for afterglow correction
self.afterglow_correction = None
self._previous_channel = None
self.afterglow_correction_enabled = device_config.get(
    'afterglow_correction_enabled', True
)
self.afterglow_delay_ms = device_config.get(
    'afterglow_correction_delay_ms', 5.0
)

if self.afterglow_correction_enabled:
    optical_cal_file = device_config.get('optical_calibration_file')
    if optical_cal_file:
        try:
            from afterglow_correction import AfterglowCorrection
            self.afterglow_correction = AfterglowCorrection(optical_cal_file)
            logger.info("✅ Afterglow correction ENABLED")
            logger.info(f"   Calibration: {Path(optical_cal_file).name}")
            logger.info(f"   Delay: {self.afterglow_delay_ms}ms")
        except Exception as e:
            logger.warning(f"⚠️ Failed to load optical calibration: {e}")
            logger.warning("⚠️ Afterglow correction DISABLED")
            self.afterglow_correction = None
    else:
        logger.info("ℹ️ No optical calibration file specified")
        logger.info("ℹ️ Afterglow correction DISABLED")
else:
    logger.info("ℹ️ Afterglow correction DISABLED (config setting)")
```

---

**Location**: `_read_channel_data` method (line ~252)

**Add after dark noise correction** (around line ~360):
```python
# Handle dark noise correction with universal resizing
if self.dark_noise.shape == averaged_intensity.shape:
    dark_correction = self.dark_noise
    # ... existing code ...
else:
    # ... existing resizing code ...

# Apply dark noise correction
subtracted = averaged_intensity - dark_correction

# ✨ NEW: Apply afterglow correction
if (self.afterglow_correction and
    self._previous_channel and
    self.afterglow_correction_enabled):
    try:
        # Get current integration time
        integration_time_ms = self.usb.integration_time_micros() / 1000.0

        # Calculate and apply correction
        afterglow_corrected = self.afterglow_correction.apply_correction(
            subtracted,
            self._previous_channel,
            integration_time_ms,
            self.afterglow_delay_ms
        )

        # Log correction (only for channel A to avoid spam)
        if ch == "a":
            correction_value = self.afterglow_correction.calculate_correction(
                self._previous_channel,
                integration_time_ms,
                self.afterglow_delay_ms
            )
            logger.debug(
                f"✨ Afterglow correction applied: Ch {self._previous_channel} → "
                f"{correction_value:.1f} counts removed"
            )

        # Use corrected signal for further processing
        subtracted = afterglow_corrected

    except Exception as e:
        logger.warning(f"⚠️ Afterglow correction failed: {e}")
        # Continue with uncorrected data
else:
    if ch == "a" and self.afterglow_correction:
        logger.debug("ℹ️ First channel - no afterglow correction")

# Store in int_data (this is used by downstream processing)
self.int_data[ch] = subtracted

# Update previous channel for next iteration
self._previous_channel = ch

# ... continue with existing code (transmittance calculation, etc.)
```

---

### **Step 3: Update `device_config.json`**

**Add new fields**:
```json
{
  "spectrometer_serial": "FLMT09788",
  "optical_fiber_diameter_um": 200,
  "led_pcb_model": "luminus_cool_white",

  "optical_calibration_file": "optical_calibration/system_FLMT09788_20251011_210859.json",
  "afterglow_correction_enabled": true,
  "afterglow_correction_delay_ms": 5.0
}
```

---

## Testing Plan

### **Test 1: Module Load Test**
```python
from afterglow_correction import AfterglowCorrection

# Load calibration
cal = AfterglowCorrection('optical_calibration/system_FLMT09788_20251011_210859.json')

# Test interpolation
tau_30ms = cal.calculate_correction('a', 30, 5)  # Non-calibrated point
tau_50ms = cal.calculate_correction('a', 50, 5)  # Calibrated point

print(f"τ @ 30ms: {tau_30ms:.2f} counts")
print(f"τ @ 50ms: {tau_50ms:.2f} counts")
```

### **Test 2: Multi-Channel Timing Test**
```python
# Run 4-channel acquisition with correction enabled
# Measure total cycle time
# Expected: ~300ms (down from ~700ms)

start = time.time()
# ... 4-channel cycle ...
elapsed = time.time() - start

print(f"4-channel cycle: {elapsed*1000:.1f}ms")
# Target: <350ms
```

### **Test 3: Correction Accuracy Test**
```python
# Run 2 measurements of same channel
# First without correction (wait 100ms)
# Second with correction (wait 5ms)

# Compare results - should be similar
difference = abs(corrected - reference) / reference * 100
print(f"Correction error: {difference:.2f}%")
# Target: <5%
```

---

## Success Criteria

### **Performance**:
✅ 4-channel scan: <350ms (target: 300ms)
✅ Acquisition frequency: ≥2 Hz
✅ Per-channel budget: <125ms

### **Accuracy**:
✅ Correction error: <5% (compared to long-delay reference)
✅ R² for corrected vs reference: >0.95
✅ No degradation in SPR peak detection

### **Robustness**:
✅ Graceful degradation if optical calibration missing
✅ No crashes or errors during acquisition
✅ Logging provides clear status

---

## Timeline

**Estimated Implementation Time**: 2-3 hours

1. **Create `afterglow_correction.py`**: 1 hour
2. **Integrate into acquisition**: 30 min
3. **Testing and validation**: 1 hour
4. **Documentation update**: 30 min

---

## Next Steps After Phase 1

### **Phase 2: Calibration Enhancement** (Medium Priority)
- Add afterglow correction to Step 5 (dark noise)
- Add afterglow correction to Step 7 (reference signals)
- Estimated time: 1-2 hours

### **Phase 3: Validation Suite** (Medium Priority)
- Create `test_optical_calibration.py`
- Interpolation accuracy tests
- Real-world correction validation
- Estimated time: 2-3 hours

---

**Status**: Ready to implement Step 1 (Create `afterglow_correction.py`)
**Next Action**: Create the correction module with cubic spline interpolation
**Last Updated**: October 11, 2025
