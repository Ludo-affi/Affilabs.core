# Adaptive Afterglow Correction System

## Overview

The afterglow correction system now **dynamically adapts** to any channel configuration:
- **ABCD loop** (all 4 channels)
- **AC loop** (channels A and C only)
- **BD loop** (channels B and D only)
- **Any other permutation**

## How It Works

### Circular Channel Sequence

The system tracks which channel was measured last and uses its afterglow parameters for correcting the current channel. The sequence is **circular**:

```
Last Channel of Cycle → First Channel of Next Cycle
```

### Channel Configuration Examples

#### Full ABCD Loop (Default)
```
Cycle 1: [D] → A → B → C → D
Cycle 2:       [D] → A → B → C → D
Cycle 3:             [D] → A → B → C → D

Corrections applied:
- Channel A uses Channel D's afterglow ✅
- Channel B uses Channel A's afterglow ✅
- Channel C uses Channel B's afterglow ✅
- Channel D uses Channel C's afterglow ✅
```

#### AC Loop
```
Cycle 1: [C] → A → C
Cycle 2:       [C] → A → C
Cycle 3:             [C] → A → C

Corrections applied:
- Channel A uses Channel C's afterglow ✅
- Channel C uses Channel A's afterglow ✅
```

#### BD Loop
```
Cycle 1: [D] → B → D
Cycle 2:       [D] → B → D
Cycle 3:             [D] → B → D

Corrections applied:
- Channel B uses Channel D's afterglow ✅
- Channel D uses Channel B's afterglow ✅
```

## Implementation Details

### 1. Initialization (First Cycle)

```python
# In __init__:
self._last_active_channel: Optional[str] = None
self._afterglow_initialized: bool = False

# At start of first cycle:
if not self._afterglow_initialized and ch_list:
    self._last_active_channel = ch_list[-1]  # Last channel in active list
    self._afterglow_initialized = True
```

**Result**: First channel in sequence gets corrected using last channel's afterglow

### 2. Per-Channel Update (Processing Thread)

```python
# After processing each channel (line ~832):
self._last_active_channel = ch
```

**Result**: Each subsequent channel uses the previous channel's afterglow

### 3. Circular Wrap-Around

Because `_last_active_channel` is updated for each channel as it's processed:
- Last channel of cycle sets `_last_active_channel = last_ch`
- First channel of next cycle uses that value
- **Automatic circular wrap-around** ✅

## Code Changes Made

### File: `utils/spr_data_acquisition.py`

**Lines 151-154** (Initialization):
```python
# OLD:
self._last_active_channel: Optional[str] = 'd'  # ❌ Hardcoded!

# NEW:
self._last_active_channel: Optional[str] = None  # ✅ Dynamic
self._afterglow_initialized: bool = False
```

**Lines 480-486** (First Cycle Initialization):
```python
# NEW CODE ADDED:
ch_list = self._get_active_channels()

if not self._afterglow_initialized and ch_list:
    self._last_active_channel = ch_list[-1]  # Last channel in active list
    self._afterglow_initialized = True
    logger.debug(f"✨ Afterglow initialized: first channel will use prev_ch='{ch_list[-1]}'")
```

**Line ~832** (Already existed, unchanged):
```python
# Update after each channel processed:
self._last_active_channel = ch
```

## Testing Scenarios

### Scenario 1: ABCD Loop
```bash
Expected log on first cycle:
✨ Afterglow initialized: first channel will use prev_ch='d'

Expected corrections:
Ch A: prev_ch='d', correction=~5-15 counts
Ch B: prev_ch='a', correction=~5-15 counts
Ch C: prev_ch='b', correction=~5-15 counts
Ch D: prev_ch='c', correction=~5-15 counts
```

### Scenario 2: AC Loop
```bash
Expected log on first cycle:
✨ Afterglow initialized: first channel will use prev_ch='c'

Expected corrections:
Ch A: prev_ch='c', correction=~5-15 counts
Ch C: prev_ch='a', correction=~5-15 counts
```

### Scenario 3: BD Loop
```bash
Expected log on first cycle:
✨ Afterglow initialized: first channel will use prev_ch='d'

Expected corrections:
Ch B: prev_ch='d', correction=~5-15 counts
Ch D: prev_ch='b', correction=~5-15 counts
```

## Afterglow Calibration Compatibility

### Current Calibration Files
Your existing afterglow calibration should already contain parameters for all 4 channels (A, B, C, D).

### When to Recalibrate

**Recalibration NOT needed if:**
- ✅ You have an existing afterglow calibration file
- ✅ Hardware hasn't changed (LEDs, optical path)
- ✅ Integration times are within calibrated range
- ✅ LED delay timing is similar (current: 20ms)

**Recalibration RECOMMENDED if:**
- ❌ No existing afterglow calibration file
- ❌ Hardware changes (new LEDs, different optical setup)
- ❌ Integration times significantly different from calibration
- ❌ Channel A still tracks differently after code fix
- ❌ You want to optimize for AC/BD loop configurations specifically

### Calibration Process
If you decide to recalibrate:
1. Run full afterglow characterization for all 4 channels
2. Measure τ (decay time), amplitude, and baseline for each channel
3. Cover integration time range: 10-100ms (typical operating range)
4. Use current LED delay: 20ms
5. Save calibration file (will work for all channel configurations)

## Benefits of Adaptive System

1. **Flexible Channel Selection**
   - No code changes needed for different channel loops
   - Automatically adapts to active channel list

2. **Consistent Correction**
   - All channels receive appropriate afterglow correction
   - No special cases or hardcoded values

3. **Easy Testing**
   - Can compare ABCD vs AC vs BD performance
   - Same calibration file works for all

4. **Production Ready**
   - Handles any channel permutation
   - Robust to configuration changes

## Verification Steps

1. **Check First Cycle Log**
   ```
   Look for: ✨ Afterglow initialized: first channel will use prev_ch='x'
   Verify: 'x' is the last channel in your active configuration
   ```

2. **Check Channel A Behavior**
   ```
   - Does Channel A track in same wavelength range as other channels?
   - Is baseline offset eliminated?
   - Does peak tracking look consistent?
   ```

3. **Check Debug Logs** (if enabled)
   ```
   Look for: ✨ Afterglow correction applied: prev_ch='x', correction=Y counts
   Verify: Corrections are being applied to all active channels
   ```

4. **Compare Channels**
   ```
   - Similar RU ranges across all channels?
   - Similar noise levels?
   - Consistent peak behavior?
   ```

## Next Steps

1. ✅ **Code Fixed**: Adaptive afterglow correction implemented
2. ⏳ **Test**: Run app and verify Channel A behavior
3. 🔍 **Evaluate**: Check if all channels track consistently
4. 📊 **Decide**: Recalibrate afterglow only if needed

---

**Status**: Ready to test with any channel configuration
**Files Modified**: `utils/spr_data_acquisition.py` (lines 151-154, 480-486)
**Compatibility**: Works with existing afterglow calibration files

