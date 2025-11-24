# Improved Afterglow Measurement Method

**Date**: November 23, 2025
**Status**: ✅ IMPLEMENTED

## Summary

Updated the afterglow calibration method based on test results showing **24% improvement in stability** and enabling **2x faster acquisition** (25ms vs 50ms).

## Previous Method (Pre-Nov 23, 2025)

```python
# OLD APPROACH
ctrl.set_intensity(ch=ch, raw_val=led_intensity)
time.sleep(0.25)  # 250ms LED on time
ctrl.set_intensity(ch=ch, raw_val=0)
time.sleep(0.01)  # Brief delay for command processing
ctrl.turn_off_channels()
time.sleep(0.05)  # Wait for LED to physically turn off
t0 = time.perf_counter()  # Start timing AFTER 50ms delay
# Measure afterglow decay...
```

**Issues:**
- Total delay before measurement: ~60ms (10ms + 50ms)
- Inconsistent LED on time (250ms)
- Artificial delay separated LED off from measurement start
- Missed early decay data (first 50ms not captured)

## Improved Method (Current)

```python
# NEW APPROACH (matches test_mode2_integration_calibration.py)
ctrl.set_intensity(ch=ch, raw_val=led_intensity)
time.sleep(0.20)  # 200ms LED on time (consistent phosphor charge)
ctrl.set_intensity(ch=ch, raw_val=0)
ctrl.turn_off_channels()
t0 = time.perf_counter()  # Start timing IMMEDIATELY after LED off
# Measure afterglow decay from t=0...
```

**Improvements:**
- No artificial delays - measure immediately after LED off
- Consistent 200ms LED on time (matches real operation method)
- Captures full decay curve including early phase (t=0 to 250ms)
- LED physically turns off within ~1-2ms, decay starts immediately

## Test Results

From `test_mode2_integration_calibration.py` validation (30-point time series):

### 25ms Fast Acquisition:
- **No correction**: σ = 27.9 counts, CV = 0.80% ✅
- **With correction**: σ = 21.2 counts, CV = ~1% ✅
- **Improvement**: 24.1% noise reduction

### 50ms Baseline:
- **Baseline**: σ = 14.7 counts, CV = 0.44% ✅

### Key Findings:
1. ✅ Afterglow correction **works properly** with improved timing
2. ✅ Previous test failure was due to measuring with LED ON (wrong!)
3. ✅ 25ms acquisition viable with correction (2x faster than 50ms)
4. ✅ Trade-off: 25ms slightly noisier than 50ms, but acceptable for fast operation

## Physical Explanation

### Why It Works:
1. **LED phosphor physics**: Decay starts immediately when LED turns off
2. **Command latency**: LED physically off within 1-2ms of software command
3. **Integration window**: Detector samples continuously, captures decay from t≈0
4. **No missed data**: Early decay phase (0-50ms) captured, improves fit quality

### Why Previous Method Failed:
- Measuring with LED ON (62,000 counts) instead of OFF (3,500 counts)
- Subtracting afterglow correction from wrong measurement
- First reading had LED transient → outliers → huge variation (CV 5.95%)
- Correction made things WORSE instead of better

### Why New Method Succeeds:
- Measuring with LED OFF captures true afterglow signal
- Correction removes phosphor decay, leaves near-zero baseline
- No LED transients (LED fully on for 200ms before turn-off)
- Stable, repeatable measurements (CV 0.8-1.0%)

## Implementation Changes

### 1. `utils/afterglow_calibration.py`:
- Updated `run_afterglow_calibration()` function signature
- Changed default `pre_on_duration_s` from 0.25 to 0.20 seconds
- Removed 50ms delay before measurement (`time.sleep(0.05)`)
- Start timing immediately after `ctrl.turn_off_channels()`
- Updated docstring with improved method description

### 2. `main_simplified.py`:
- Updated `_run_afterglow_then_led_calibration()` method
- Changed pre_on_duration_s parameter from 0.25 to 0.20
- Added comments explaining improved timing approach

### 3. `settings/settings.py`:
- Added clarifying comment to `LED_DELAY`
- Note: LED_DELAY is for signal acquisition, NOT afterglow measurement
- Afterglow calibration uses immediate measurement (no delay)

## Recommendations

### For Normal Operation (50ms):
- Use current settings with afterglow correction
- Excellent stability: σ = 14.7 counts
- Well-tested, conservative approach

### For Fast Operation (25ms):
- **Enable afterglow correction** (24% noise reduction)
- Good stability: σ = 21.2 counts
- 2x faster acquisition vs 50ms
- Trade-off: Slightly more noise, but acceptable

### Future Optimization:
- Consider making LED on time configurable (currently 200ms)
- Could test shorter times (150ms, 100ms) for faster calibration
- Must ensure phosphor fully charged for consistent amplitude

## Files Modified

1. ✅ `utils/afterglow_calibration.py` - Core measurement method
2. ✅ `main_simplified.py` - Calibration workflow integration
3. ✅ `settings/settings.py` - Documentation clarification
4. ✅ `IMPROVED_AFTERGLOW_METHOD.md` - This summary document

## Validation Status

✅ Tested on real hardware (USB4000 S/N: FLMT09116)
✅ All 4 channels validated (A, B, C, D)
✅ 30-point time series confirms stability
✅ Afterglow correction improves noise by 24%
✅ Method matches operational timing (200ms LED on)

## Physics Parameters

From test results (after dark subtraction):

**Decay Constants (τ)**:
- Channel A: 75.1ms
- Channel B: 61.1ms
- Channel C: 64.1ms
- Channel D: 64.3ms

**Afterglow Amplitude @ 50ms**:
- Channel A: 249 counts (0.42% of peak)
- Channel B: 204 counts (0.33% of peak)
- Channel C: 235 counts (0.38% of peak)
- Channel D: 206 counts (0.40% of peak)

**Dark Signal**: 3166 ± 8 counts (must be subtracted)

## Conclusion

The improved afterglow measurement method provides:
1. ✅ **Better data quality** - captures full decay curve from t=0
2. ✅ **Improved stability** - 24% noise reduction with correction
3. ✅ **Faster acquisition** - enables 25ms operation (2x speed)
4. ✅ **Correct physics** - measures what we intend (afterglow, not signal)
5. ✅ **Simpler implementation** - removes artificial delays

This method should be used for all future afterglow calibrations.
