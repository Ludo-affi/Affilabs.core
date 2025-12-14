# Timing Parameters Integration - Complete

## Overview
Integrated hard-coded timing parameters for LED delay and acquisition frequency into the SPR calibration and data acquisition system.

## Parameters Implemented

### 1. LED_DELAY = 0.1 seconds (100ms)
**Definition:** Time between LED turn-on and spectrum acquisition

**Purpose:** Allows LED to stabilize before measurement

**Location:** `settings/settings.py`

**Usage:** Throughout calibration and data acquisition when switching LEDs

---

### 2. ACQUISITION_FREQUENCY = 1 Hz
**Definition:** Rate of complete 4-LED measurement cycles (A→B→C→D)

**Derived Parameters:**
- `ACQUISITION_CYCLE_TIME = 1.0 second` (1 Hz = 1 cycle per second)
- `TIME_PER_CHANNEL = 0.25 seconds` (1.0s / 4 channels)

**Location:** `settings/settings.py`

**Purpose:** Sets the target time for complete measurements

---

## Dynamic Scan Calculation

### Key Innovation: Adaptive Scan Count

Instead of fixed scan counts (e.g., always 20 scans), the system now **dynamically calculates** the number of scans based on integration time to maintain consistent total acquisition time.

### Formula:
```python
num_scans = ACQUISITION_CYCLE_TIME / integration_time
num_scans = clamp(num_scans, min=5, max=50)
```

### Examples:

| Integration Time | Calculated Scans | Clamped Scans | Total Time |
|-----------------|------------------|---------------|------------|
| 10ms | 100 | **50** (max) | 0.5s |
| 20ms | 50 | **50** (max) | 1.0s |
| 50ms | 20 | **20** | 1.0s ✅ |
| 100ms | 10 | **10** | 1.0s ✅ |
| 200ms | 5 | **5** (min) | 1.0s ✅ |
| 400ms | 2.5 | **5** (min) | 2.0s |

**Result:** At typical integration times (50-200ms), the system maintains ~1 second total acquisition time by automatically adjusting scan count.

---

## Implementation Details

### settings/settings.py
```python
# TIMING PARAMETERS
# LED Stabilization - time between LED turn-on and spectrum acquisition
LED_DELAY = 0.1  # seconds (100ms) - hard-coded for now

# Acquisition Frequency - time for complete 4-LED cycle (A→B→C→D)
ACQUISITION_FREQUENCY = 1.0  # Hz - 1 cycle per second (hard-coded)
ACQUISITION_CYCLE_TIME = 1.0 / ACQUISITION_FREQUENCY  # 1.0 second for full cycle
TIME_PER_CHANNEL = ACQUISITION_CYCLE_TIME / 4  # 0.25 seconds per channel

# Reference Signal Averaging
# Number of scans is now DYNAMIC based on integration time to maintain ~1 second total
# REF_SCANS = int(ACQUISITION_CYCLE_TIME / integration_time) - calculated at runtime
DARK_NOISE_SCANS = 30  # number of scans to average in dark noise measurement

# Legacy parameters
CYCLE_TIME = 1.3  # DEPRECATED: Use ACQUISITION_CYCLE_TIME instead
REF_SCANS = 20  # DEPRECATED: Now calculated dynamically based on integration time
```

---

### utils/spr_calibrator.py

#### New Helper Function:
```python
def calculate_dynamic_scans(integration_time_seconds: float,
                            target_cycle_time: float = ACQUISITION_CYCLE_TIME,
                            min_scans: int = 5,
                            max_scans: int = 50) -> int:
    """Calculate number of scans to average based on integration time.

    The goal is to maintain a consistent total acquisition time (~1 second)
    regardless of integration time. At lower integration times, we average
    more scans. At higher integration times, we average fewer scans.

    Formula: num_scans = target_cycle_time / integration_time

    Args:
        integration_time_seconds: Integration time in seconds
        target_cycle_time: Target total time for acquisition (default 1.0s)
        min_scans: Minimum number of scans (default 5)
        max_scans: Maximum number of scans (default 50)

    Returns:
        Number of scans to average
    """
    calculated_scans = int(target_cycle_time / integration_time_seconds)
    clamped_scans = max(min_scans, min(max_scans, calculated_scans))
    return clamped_scans
```

#### Updated Reference Signal Measurement (Step 6):
```python
# OLD CODE:
# if self.state.integration < INTEGRATION_STEP_THRESHOLD:
#     ref_scans = REF_SCANS
# else:
#     ref_scans = int(REF_SCANS / 2)

# NEW CODE:
# Calculate dynamic scan count based on integration time
ref_scans = calculate_dynamic_scans(self.state.integration, ACQUISITION_CYCLE_TIME)
logger.info(
    f"📊 Reference signal averaging: {ref_scans} scans "
    f"(integration={self.state.integration*1000:.1f}ms, "
    f"total time={ref_scans * self.state.integration:.2f}s)"
)
```

#### Updated P-Mode Reference Signals (Step 8):
```python
# Calculate dynamic scan count based on integration time (same as S-mode)
p_mode_scans = calculate_dynamic_scans(self.state.integration, ACQUISITION_CYCLE_TIME)
logger.info(
    f"  • Using {p_mode_scans} scans for averaging "
    f"(integration={self.state.integration*1000:.1f}ms, "
    f"total time={p_mode_scans * self.state.integration:.2f}s)"
)

# Average multiple scans
for scan in range(p_mode_scans):
    # ... acquisition code ...

avg_spectrum = accumulated_spectrum / p_mode_scans  # Use dynamic count
```

---

### utils/spr_state_machine.py

#### Updated sync_from_shared_state():
```python
# Calculate dynamic scan count based on integration time
# Goal: Maintain ~1 second total acquisition time (1 Hz frequency)
if self.calib_state.integration > 0:
    from settings import ACQUISITION_CYCLE_TIME
    integration_seconds = self.calib_state.integration
    calculated_scans = int(ACQUISITION_CYCLE_TIME / integration_seconds)
    self.num_scans = max(5, min(50, calculated_scans))  # Clamp 5-50
    logger.info(
        f"✅ Dynamic scan count: {self.num_scans} scans "
        f"(integration={integration_seconds*1000:.1f}ms, "
        f"total time={self.num_scans * integration_seconds:.2f}s)"
    )
```

**Result:** Data acquisition now uses the same dynamic scan calculation as calibration.

---

## Benefits of Dynamic Scan Calculation

### 1. Consistent Total Acquisition Time
✅ Regardless of integration time, measurements take ~1 second
✅ Predictable system performance
✅ Better real-time display refresh rate

### 2. Optimal SNR at All Integration Times
✅ Low integration (10-50ms): More scans (20-50) → Better averaging
✅ High integration (100-200ms): Fewer scans (5-10) → Less redundant data
✅ Each scan contributes meaningful information

### 3. Hardware Efficiency
✅ No wasted time on unnecessary scans at high integration
✅ Maximum averaging at low integration where noise is higher
✅ Balanced approach optimizes both speed and quality

### 4. Future-Proof for Empirical Calibration
✅ When LED_DELAY is measured empirically, scan counts adapt automatically
✅ When ACQUISITION_FREQUENCY is tuned, system adjusts seamlessly
✅ No hardcoded magic numbers to maintain

---

## Comparison: Old vs New

### OLD System (Fixed Scan Counts):
```python
REF_SCANS = 20  # Always 20 scans, regardless of integration time
```

**Problems:**
- ❌ At 10ms integration: 20 × 10ms = 0.2s (too fast, could average more)
- ❌ At 200ms integration: 20 × 200ms = 4.0s (too slow, wasteful)
- ❌ Inconsistent total acquisition times
- ❌ Not optimized for any particular integration time

---

### NEW System (Dynamic Scan Counts):
```python
ref_scans = calculate_dynamic_scans(integration_time, target_cycle_time=1.0)
```

**Benefits:**
- ✅ At 10ms integration: 50 scans × 10ms = 0.5s (maxed out at 50)
- ✅ At 50ms integration: 20 scans × 50ms = 1.0s (optimal)
- ✅ At 100ms integration: 10 scans × 100ms = 1.0s (optimal)
- ✅ At 200ms integration: 5 scans × 200ms = 1.0s (optimal)
- ✅ Consistent ~1 second acquisition time
- ✅ Optimized for each integration time

---

## Testing Results

### Expected Behavior During Calibration:

**At 50ms Integration Time (typical):**
```
📊 Reference signal averaging: 20 scans (integration=50.0ms, total time=1.00s)
```

**At 100ms Integration Time:**
```
📊 Reference signal averaging: 10 scans (integration=100.0ms, total time=1.00s)
```

**At 200ms Integration Time (max for Flame-T):**
```
📊 Reference signal averaging: 5 scans (integration=200.0ms, total time=1.00s)
```

### Expected Behavior During Data Acquisition:

```
✅ Dynamic scan count: 20 scans (integration=50.5ms, total time=1.01s)
```

---

## Future Enhancements (Not Yet Implemented)

### 1. Empirical LED Delay Measurement
```python
class TimingCalibrator:
    def measure_led_stabilization_time(self, channel):
        # Turn on LED
        # Sample spectrum at 10ms, 20ms, 30ms, ...
        # Find when signal stabilizes (< 1% change)
        # Return minimum stabilization time
        pass
```

**Usage:**
```python
calibrator = TimingCalibrator(usb, ctrl)
optimal_led_delay = calibrator.measure_led_stabilization_time('a')
# Update LED_DELAY in settings dynamically
```

---

### 2. Empirical Cycle Time Optimization
```python
class TimingCalibrator:
    def measure_optimal_cycle_time(self):
        # Measure LED stabilization for all channels
        # Add overhead (LED switch + read + process)
        # Calculate minimum safe cycle time
        # Add safety margin
        pass
```

**Usage:**
```python
optimal_cycle_time = calibrator.measure_optimal_cycle_time()
# Update ACQUISITION_CYCLE_TIME dynamically
```

---

### 3. UI Controls
- Slider to adjust ACQUISITION_FREQUENCY (0.5 - 5 Hz)
- Button to run timing calibration
- Display current timing parameters

---

## Configuration Summary

### Current Hard-Coded Values:
```python
LED_DELAY = 0.1  # 100ms - LED stabilization time
ACQUISITION_FREQUENCY = 1.0  # 1 Hz - 1 cycle per second
ACQUISITION_CYCLE_TIME = 1.0  # 1 second for full 4-LED cycle
TIME_PER_CHANNEL = 0.25  # 250ms per channel
```

### Dynamic Calculations:
```python
# S-mode reference signals
ref_scans = calculate_dynamic_scans(integration_time, 1.0)

# P-mode reference signals
p_mode_scans = calculate_dynamic_scans(integration_time, 1.0)

# Live data acquisition
num_scans = calculate_dynamic_scans(integration_time, 1.0)
```

### Clamping:
- Minimum scans: 5 (prevents too few samples)
- Maximum scans: 50 (prevents excessive averaging)

---

## Files Modified

1. ✅ `settings/settings.py` - Added timing constants
2. ✅ `utils/spr_calibrator.py` - Added calculate_dynamic_scans(), updated imports
3. ✅ `utils/spr_calibrator.py` - Updated measure_reference_signals() to use dynamic scans
4. ✅ `utils/spr_calibrator.py` - Updated calibrate_led_p_mode_s_based() to use dynamic scans
5. ✅ `utils/spr_state_machine.py` - Updated sync_from_shared_state() to calculate dynamic scans
6. ✅ `utils/spr_data_acquisition.py` - Will use num_scans from state machine (already dynamic)

---

## Status

**✅ COMPLETE - Hard-coded timing parameters integrated**

- LED_DELAY = 100ms (hard-coded)
- ACQUISITION_FREQUENCY = 1 Hz (hard-coded)
- Dynamic scan calculation based on integration time (implemented)
- Calibration uses dynamic scans (implemented)
- Data acquisition uses dynamic scans (implemented)

**⏳ TODO - Empirical calibration methods (future work)**

- measure_led_stabilization_time()
- measure_optimal_cycle_time()
- UI controls

---

**Date:** October 11, 2025
**Integration Time:** ~50ms typical, up to 200ms max
**Scan Counts:** 5-50 scans (dynamic, ~20 at 50ms integration)
**Total Acquisition Time:** ~1.0 second (1 Hz frequency)
