# Adaptive Integration Calibration - 50k Counts Optimization

**Module:** `src/utils/calibration_adaptive_integration.py`
**Main Function:** `perform_adaptive_integration_calibration()`
**Core Algorithm:** `calibrate_integration_time_per_channel()`

## Status: ✅ INTEGRATED BUT DISABLED

The proven 50k counts optimization algorithm from `test_max_speed_50k_counts.py` has been integrated into a dedicated modern calibration module but is **currently disabled** to avoid interference with the existing fixed integration time architecture.

---

## What Was Integrated

### Algorithm: Adaptive Integration Time Optimization
**Source:** `test_max_speed_50k_counts.py` (validated 2025-11-28)

**Module:** `src/utils/calibration_adaptive_integration.py`

**Key Features:**
- **Fixed LED intensity**: All channels at 255 (maximum brightness)
- **Variable integration time**: Optimized per channel (21-63ms)
- **Target**: 50,000 counts per channel (optimal SNR)
- **Iterative optimization**: Adaptive integration increases based on signal ratio
- **Max integration**: 300ms configurable (allows reaching 50k on all channels)

---

## Validated Performance

From `test_max_speed_50k_counts.py` test results:

| Metric | Value | Notes |
|--------|-------|-------|
| **Throughput** | 1.51 Hz | 660ms/cycle for 4 channels |
| **Speed improvement** | 51% faster | vs 1.0 Hz target (1000ms) |
| **Noise** | 0.22-0.63% | Excellent precision across all channels |
| **Target achievement** | 50,000 counts | ALL channels hit target |
| **Channel A** | 63ms, 51,007 counts | 0.22% noise |
| **Channel B** | 23ms, 50,939 counts | 0.63% noise |
| **Channel C** | 21ms, 50,984 counts | 0.26% noise |
| **Channel D** | 54ms, 51,180 counts | 0.29% noise |

---

## Comparison: Standard vs Alternative Mode

### Current Standard Mode (Enabled)
```python
USE_ALTERNATIVE_CALIBRATION = False  # Current production
```

**Characteristics:**
- **Integration time**: ONE global value (e.g., 210ms)
- **LED intensity**: VARIABLE per channel (optimized individually)
- **Architecture**: Fixed integration, adjust LED to reach target
- **Typical performance**: ~1.0 Hz, 30-40k counts, 0.5-1.0% noise

**Best for:**
- Current codebase architecture
- Systems requiring uniform timing across channels
- Circular polarizers where LED affects polarization coupling

---

### Adaptive Integration Mode (Integrated, Disabled)
```python
USE_ALTERNATIVE_CALIBRATION = True  # Enable when ready
```

**Module:** `calibration_adaptive_integration.py`

**Characteristics:**
- **LED intensity**: FIXED at 255 (all channels)
- **Integration time**: VARIABLE per channel (21-63ms optimized)
- **Architecture**: Per-channel integration, LEDs at max brightness
- **Validated performance**: 1.51 Hz, 50k counts, 0.22-0.63% noise

**Advantages:**
- **51% faster** than standard mode (1.51 Hz vs 1.0 Hz)
- **Better LED stability** - all at optimal 255 intensity
- **Lower noise** - 0.22-0.63% vs typical 0.5-1.0%
- **Higher signal** - 50k vs typical 30-40k counts
- **Optimal SNR** - proven in test validation

**Trade-offs:**
- Requires per-channel integration time support in live acquisition
- Different architecture (variable timing per channel)
- Migration needed for existing code

---

## How to Enable (When Ready)

### Step 1: Enable in Settings
**File:** `src/settings/settings.py`

```python
# Change from:
USE_ALTERNATIVE_CALIBRATION = False

# To:
USE_ALTERNATIVE_CALIBRATION = True
```

### Step 2: Verify Calibration
Run a calibration and verify results:
- All channels should show LED=255
- Integration times should vary by channel (21-63ms range)
- Peak counts should be near 50,000 for all channels
- Noise should be <1% for all channels

### Step 3: Update Live Acquisition (Required)
The live acquisition system needs to be updated to use per-channel integration times:

**Current (Standard mode):**
```python
# Set ONE global integration time
detector.set_integration(integration_time)  # e.g., 210ms

# Acquire all channels with same timing
for channel in ['a', 'b', 'c', 'd']:
    spectrum = acquire_channel(channel)
```

**Required (Alternative mode):**
```python
# Set integration time PER CHANNEL
for channel in ['a', 'b', 'c', 'd']:
    integration = per_channel_integration[channel]  # e.g., 21-63ms
    detector.set_integration(integration)
    spectrum = acquire_channel(channel)
```

**Files to modify:**
- `src/core/data_acquisition_manager.py` - Main acquisition loop
- Look for `set_integration()` calls
- Add per-channel integration time logic

### Step 4: Test Thoroughly
- Run full calibration with Alternative mode enabled
- Verify live acquisition works with per-channel timing
- Check data quality, noise levels, and throughput
- Validate QC passes on all channels

---

## Technical Details

### Optimization Algorithm
From `calibrate_integration_per_channel()`:

```python
# Start at minimum integration
integration = 10.0  # Hardware minimum

# Iteratively increase until target reached
for attempt in range(5):
    # Read signal at current integration
    peak_counts = measure_signal(integration)

    # Check if close to target
    if peak_counts >= target * 0.9:
        break  # Close enough

    # Calculate needed ratio
    needed_ratio = target_counts / peak_counts

    # Increase integration adaptively
    integration = min(integration * needed_ratio * 1.1, max_integration)
```

**Key differences from Standard mode:**
- No LED adjustment - always 255
- Adaptive integration increases (not fixed steps)
- Higher target (50k vs typical 30-40k)
- Longer max integration allowed (300ms vs 70ms budget)

### Storage Format
Alternative mode stores data differently in `device_config.json`:

```json
{
  "led_calibration": {
    "integration_time_ms": 63,  // MAX across all channels
    "s_mode_intensities": {
      "a": 255,  // FIXED at 255
      "b": 255,
      "c": 255,
      "d": 255
    },
    "per_channel_integration": {  // NEW: per-channel times
      "a": 63,
      "b": 23,
      "c": 21,
      "d": 54
    }
  }
}
```

---

## Current Status

### ✅ Completed
- [x] Algorithm integrated from test_max_speed_50k_counts.py
- [x] Function updated: `calibrate_integration_per_channel()`
- [x] Documentation added with validated performance metrics
- [x] Mode disabled in settings (USE_ALTERNATIVE_CALIBRATION = False)
- [x] No interference with current Standard mode

### 📋 Ready for Migration (When Needed)
- [ ] Enable in settings (USE_ALTERNATIVE_CALIBRATION = True)
- [ ] Update live acquisition for per-channel integration
- [ ] Test full calibration → acquisition pipeline
- [ ] Validate performance matches test results

### 🎯 Expected Outcome After Migration
- **Speed**: 51% faster (1.51 Hz vs 1.0 Hz)
- **Signal**: 50k counts on all channels
- **Noise**: <0.7% on all channels
- **LED stability**: All channels at 255 (optimal)

---

## Safety Notes

⚠️ **The Alternative mode is currently DISABLED** and will have **ZERO impact** on:
- Current calibration behavior
- Fixed integration time architecture
- Live acquisition system
- Any production measurements

✅ **Safe to keep in codebase** - ready for deployment when architecture migration is complete.

---

## References

**Test Validation:**
- `test_max_speed_50k_counts.py` - Proven algorithm
- `test_fixed_integration_variable_led.py` - Comparison test showing fixed integration doesn't work for 50k target

**Modified Files:**
- `src/utils/_legacy_led_calibration.py` - Algorithm integration
- `src/settings/settings.py` - Mode control flag (disabled)

**Test Results:** Validated 2025-11-28
- 1.51 Hz throughput ✅
- 50k counts all channels ✅
- 0.22-0.63% noise ✅
- LED=255 all channels ✅

---

**Last Updated:** 2025-11-28
**Status:** Ready for deployment (currently disabled)
**Contact:** Review test results before enabling
