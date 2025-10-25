# Live Mode Smart Boost Implementation

**Date**: October 25, 2025
**Purpose**: Optimize live P-pol measurement signal while maintaining safety and performance constraints

---

## 📋 Overview

This document explains the **Smart Boost** system for live mode measurements and the **10-second display delay** for multi-point processing stabilization.

### Problem Statement

1. **Signal Dampening**: P-pol measurements have ~30-40% lower signal than S-pol calibration baseline
2. **Multi-Point Processing**: Temporal filters, Kalman filters, and peak tracking need time to converge
3. **Safety Constraints**: Must avoid saturation (65,535 counts) and stay within 200ms time budget

### Solution Architecture

**Smart Boost Strategy:**
- 🔒 **LED Intensities**: FIXED from Step 6 calibration (never change)
- ⚡ **Integration Time**: Boosted 20-40% to compensate for P-pol dampening
- 🛡️ **Safety Limits**: Enforce saturation threshold and 200ms budget
- 🕐 **Display Delay**: Hide sensorgram for first 10 seconds while processing stabilizes

---

## 🎯 Design Requirements

### 1. LED Intensity Policy

**Requirement**: LED intensities from Step 6 are the main parameters passed to live data and **never change**.

**Implementation**:
- Step 6 calibrates LED intensities for S-pol baseline (50% detector target)
- These values are stored in `state.leds_calibrated` and synced to live mode
- Live mode uses **exact same LED values** (no adjustment)
- Location: `utils/spr_state_machine.py` lines 550-557

```python
# LED policy: Use Step 6 calibrated values directly (NO adjustment)
self.live_led_intensities = {
    ch: int(self.calibrator.get_led_for_live(ch))
    for ch in CH_LIST
}
```

### 2. Integration Time Boost

**Requirement**: Global integration time can be bumped up by 20%-40% to offset P-pol signal dampening.

**Implementation**:
- Calibration target: 50% detector max (conservative for optimization)
- Live mode target: 90% detector max (maximizes signal for measurement)
- Boost factor: 90% / 50% = 1.8× desired, capped at **1.4× (40% increase)**
- Rationale: Conservative 40% boost is safe, effective, and stays within budget

**Settings** (`settings/settings.py`):
```python
TARGET_INTENSITY_PERCENT = 50  # Calibration baseline (S-pol)
LIVE_MODE_TARGET_INTENSITY_PERCENT = 90  # Live mode goal (P-pol compensated)
LIVE_MODE_MAX_BOOST_FACTOR = 1.4  # Cap at 40% increase (1.2-1.4× = 20-40%)
LIVE_MODE_MIN_BOOST_FACTOR = 1.0  # Never reduce below calibration
```

### 3. Smart Boost Constraints

**Requirement**: Stay below saturation AND within 200ms time budget per spectrum.

**Implementation**:
- **Saturation threshold**: 92% detector max (~60,400 counts for 65,535 max)
- **Time budget**: `integration × scans ≤ 200ms` per spectrum
- **Safety logic**: If boosted integration × scans > 200ms, cap at 200ms

**Per-Channel Mode** (lines 560-580 in `spr_state_machine.py`):
```python
for ch, base_int in integration_per_channel.items():
    boosted = float(base_int) * boost_factor  # Apply 1.2-1.4× boost

    # Cap at 200ms budget
    if boosted > max_integration_seconds:
        boosted = max_integration_seconds
        logger.warning(f"Channel {ch}: Boost capped at 200ms budget")

    self.live_integration_per_channel[ch] = boosted

# Force scans=1 in per-channel mode (each channel gets full 200ms budget)
self.num_scans = 1
```

**Global Mode** (lines 595-615 in `spr_state_machine.py`):
```python
# Apply boost to integration time
live_integration_seconds = integration_seconds * boost_factor

# Cap at 200ms budget
if live_integration_seconds > max_integration_seconds:
    live_integration_seconds = max_integration_seconds

# Calculate dynamic scans to fill 200ms budget
self.num_scans = calculate_dynamic_scans(live_integration_seconds)
# Example: 50ms integration × 4 scans = 200ms total
```

### 4. Display Delay for Processing Stabilization

**Requirement**: Don't display the first 10 seconds because we need to make sure data processing that requires multiple points kicks in.

**Implementation**:
- Data collection starts immediately (no delay)
- Display is hidden for first 10 seconds
- Multi-point algorithms converge during this time:
  - Temporal mean filter (5-point window)
  - Kalman filter (optimal state estimation)
  - Peak tracking (centroid, derivative, consensus)
  - Savitzky-Golay smoothing (11-point window)

**Code Location** (`widgets/datawindow.py`):

```python
# __init__ method (lines 247-255)
from settings import LIVE_MODE_DISPLAY_DELAY_SECONDS
self.display_delay_seconds = LIVE_MODE_DISPLAY_DELAY_SECONDS  # 10.0 seconds
self.display_enabled = False  # Will be enabled after delay
self.live_start_time = None  # Set when first data arrives

# update_data method (lines 575-610)
# Track start time from first data arrival
if self.live_start_time is None and "start" in app_data:
    self.live_start_time = app_data["start"]
    logger.info("🕐 DISPLAY DELAY: 10s for processing stabilization")

# Calculate elapsed time
elapsed_time = time.time() - self.live_start_time

# Enable display after delay
if not self.display_enabled and elapsed_time >= self.display_delay_seconds:
    self.display_enabled = True
    logger.info("✅ DISPLAY ENABLED - stabilization complete")

# Skip plot updates during delay (but collect data)
if not self.display_enabled:
    self.data = app_data  # Collect data silently
    # Update clock to show progress
    remaining = max(0, self.display_delay_seconds - elapsed_time)
    self.ui.status.setText(f"Stabilizing... Display in {remaining:.0f}s")
    return  # Don't update plots yet
```

---

## 📊 Example Calculation

**Given** (from recent calibration):
- Step 6 integration time: 33.7ms
- Step 6 LED values: A=129, B=255, C=31, D=33
- Calibration target: 50% detector (49,151 counts)

**Live Mode Boost**:
- Target: 90% detector (59,000 counts)
- Desired boost: 90% / 50% = 1.8×
- **Applied boost: 1.4× (capped at 40% max)**
- Boosted integration: 33.7ms × 1.4 = **47.2ms**

**Per-Channel Mode**:
- Integration: 47.2ms per channel
- Scans: 1 (fixed)
- Time per spectrum: 47.2ms × 1 = 47.2ms ✅ (within 200ms budget)
- Cycle time: 47.2ms × 4 channels + overhead = ~250ms (~4 Hz update rate)

**Signal Level**:
- S-pol baseline: 49,151 counts @ 33.7ms
- P-pol with boost: 49,151 × 1.4 × 0.7 (P-pol factor) = **~48,000 counts** ✅
- Saturation threshold: 60,400 counts (92% detector)
- Safety margin: 12,400 counts (20%) ✅

---

## 🔍 Validation Criteria

### Pre-Flight Checklist

- ✅ LED intensities match Step 6 exactly (no adjustment in live mode)
- ✅ Boost factor between 1.0× and 1.4× (20-40% increase)
- ✅ Boosted integration × scans ≤ 200ms per spectrum
- ✅ Expected signal level < 92% detector (no saturation)
- ✅ Display hidden for first 10 seconds
- ✅ Status message shows "Stabilizing... Display in Xs"
- ✅ Display enables automatically after 10s with confirmation message

### Success Metrics

**Signal Quality**:
- P-pol signal: 45,000-55,000 counts (70-85% of detector max)
- No saturation warnings (all channels < 60,400 counts)
- Stable baseline after 10-second stabilization period

**Performance**:
- Update rate: 3-5 Hz (4 channels × 50ms + overhead)
- No dropped frames during 10-second stabilization
- Smooth sensorgram after display enabled

**Processing Stability**:
- Peak tracking stable within ±1 RU after 10 seconds
- Temporal filter converged (5-point window filled)
- Kalman filter state estimation optimal

---

## 🛠️ Configuration

### Adjustable Parameters

**Settings File** (`settings/settings.py`):

```python
# Smart Boost Configuration
LIVE_MODE_TARGET_INTENSITY_PERCENT = 90  # Target signal (90% detector)
LIVE_MODE_SATURATION_THRESHOLD_PERCENT = 92  # Safety threshold
LIVE_MODE_MIN_BOOST_FACTOR = 1.0  # Never reduce below calibration
LIVE_MODE_MAX_BOOST_FACTOR = 1.4  # Maximum 40% increase

# Time Budget
LIVE_MODE_MAX_INTEGRATION_MS = 200.0  # Maximum per spectrum

# Display Delay
LIVE_MODE_DISPLAY_DELAY_SECONDS = 10.0  # Stabilization period
```

### Tuning Guidelines

**If signal too low** (< 40,000 counts):
- Increase `LIVE_MODE_MAX_BOOST_FACTOR` from 1.4 to 1.6 (60% boost)
- **WARNING**: Check for saturation on brightest channels

**If saturation occurs** (> 60,400 counts):
- Decrease `LIVE_MODE_TARGET_INTENSITY_PERCENT` from 90 to 85
- Or decrease `LIVE_MODE_MAX_BOOST_FACTOR` from 1.4 to 1.2 (20% boost)

**If processing not stable after 10s**:
- Increase `LIVE_MODE_DISPLAY_DELAY_SECONDS` from 10.0 to 15.0
- Check temporal filter window size (should be 5 points minimum)

**If update rate too slow**:
- System is already optimized at ~200ms per channel
- Cannot reduce further without sacrificing SNR
- Consider reducing display update frequency (GUI throttling)

---

## 📝 Implementation Log

### Files Modified

1. **`settings/settings.py`** (lines 358-373)
   - Updated boost configuration with conservative 20-40% range
   - Added saturation threshold parameter
   - Added display delay parameter
   - Improved documentation

2. **`utils/spr_state_machine.py`** (lines 520-580)
   - Updated boost calculation with smart constraints
   - Added safety checks for 200ms budget and saturation
   - Improved logging for transparency
   - Confirmed LED policy: FIXED from Step 6

3. **`widgets/datawindow.py`** (lines 235-255, 560-610)
   - Added display delay initialization
   - Implemented 10-second stabilization logic
   - Added status messages for user feedback
   - Data collection continues silently during delay

### Testing Plan

**Test 1: LED Intensity Verification**
- Run calibration, note Step 6 LED values
- Start live mode, check LED values in logs
- **Expected**: Exact match (no adjustment)

**Test 2: Boost Factor Validation**
- Check logs for "Applied boost: X.XX×"
- **Expected**: Between 1.0× and 1.4×

**Test 3: Budget Compliance**
- Calculate: boosted_integration × scans
- **Expected**: ≤ 200ms per spectrum

**Test 4: Signal Level Check**
- Monitor per-channel signals in live mode
- **Expected**: 45,000-55,000 counts (no saturation)

**Test 5: Display Delay**
- Start live mode, observe status message
- **Expected**: "Stabilizing... Display in Xs" for 10 seconds
- **Expected**: Plots appear after 10s with confirmation message

**Test 6: Processing Stability**
- Wait 15 seconds, observe peak tracking
- **Expected**: Stable within ±1 RU (no drift)

---

## ✅ Validation Results

*To be filled after testing with hardware*

**Calibration Results**:
- Integration time: _____ ms
- LED values: A=___, B=___, C=___, D=___

**Live Mode Results**:
- Boost factor: _____ × (_____ %)
- Boosted integration: _____ ms
- Scans per channel: _____
- LED values: A=___, B=___, C=___, D=___ (should match calibration)

**Signal Levels** (after 10s stabilization):
- Channel A: _____ counts
- Channel B: _____ counts
- Channel C: _____ counts
- Channel D: _____ counts
- **Status**: PASS / FAIL (all < 60,400 counts?)

**Performance**:
- Update rate: _____ Hz
- Display delay: _____ seconds observed
- Stabilization message: YES / NO
- Peak stability: ±_____ RU

---

## 📚 References

- **Calibration Documentation**: `CALIBRATION_S_REF_QC_SYSTEM.md`
- **Step 4 Retry Fix**: `STEP4_RETRY_LOOP_FIX.md`
- **P-pol Data Flow**: `PPOL_DATA_FLOW_EXPLAINED.md`
- **Integration Time Optimization**: `INTEGRATION_TIME_OPTIMIZATION.md`

---

## 🎓 Key Takeaways

1. **LED values are sacred**: Once calibrated in Step 6, they never change in live mode
2. **Integration time is the control knob**: Boost 20-40% to compensate for P-pol dampening
3. **Safety is paramount**: Enforce saturation threshold and 200ms budget at all times
4. **Processing needs time**: 10-second delay ensures multi-point algorithms converge
5. **Transparency matters**: Log all decisions so users understand what's happening

**Philosophy**: *"Measure twice, cut once"* - Conservative boost with strong safety constraints ensures reliable, reproducible measurements.
