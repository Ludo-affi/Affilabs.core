# Channel 'd' Sensorgram Display Fix

## Issue Summary
User reported two problems:
1. **Channel 'd' not visible** in the top sensorgram graph
2. **Bottom sensorgram display** showing no data

## Root Cause Analysis

### Investigation Process
1. ✅ Verified all 4 channels (a, b, c, d) are included in `CH_LIST`
2. ✅ Verified `lambda_values` dictionary initialized with all 4 channels
3. ✅ Verified sensorgram_data() returns data for all 4 channels
4. ✅ Verified UI has checkboxes for all 4 channels (all checked by default)
5. ✅ Verified SensorgramGraph creates plots for all 4 channels
6. ✅ Verified signal connections exist for checkbox changes
7. ❌ **FOUND**: No initialization of plot visibility from checkbox state

### Root Cause
**Plot visibility not synchronized with checkbox state on startup**

**What Was Happening:**
- Checkboxes are checked by default in UI (`segment_D.setChecked(True)`)
- Plots are created for all channels but visibility state is undefined
- Signal connections only trigger when checkbox state *changes*
- On startup, checkboxes are already checked, so no stateChanged signal fires
- Result: Plot visibility may default to False even though checkbox is checked

**The Critical Code:**
```python
# widgets/graphs.py - SensorgramGraph.update()
for ch in CH_LIST:
    if not self.plots[ch].isVisible():  # ⚠️ This check fails for channel 'd'
        logger.debug(f"Skipping hidden channel {ch}")
        continue  # Plot data is skipped!
```

## Solution Implemented

### Fix #1: Initialize Plot Visibility (Primary Fix)
**File:** `widgets/datawindow.py`
**Location:** After signal connections in `__init__()` method

```python
# ✅ FIX: Initialize plot visibility to match checkbox state
# This ensures all checked checkboxes (including 'd') show their plots
for ch in CH_LIST:
    checkbox = getattr(self.ui, f"segment_{ch.upper()}")
    is_checked = checkbox.isChecked()
    self.full_segment_view.display_channel_changed(ch, is_checked)
    self.SOI_view.display_channel_changed(ch, is_checked)
    logger.debug(f"Initialized channel {ch} visibility: {is_checked}")
```

**What This Does:**
- Reads the checkbox state for each channel
- Calls `display_channel_changed()` to set plot visibility
- Ensures plots match checkbox state before any user interaction
- Logs the initialization for debugging

### Fix #2: Enhanced Debug Logging
**File:** `widgets/graphs.py`
**Location:** SensorgramGraph.update() method

```python
# 🐛 DEBUG: Log data availability for each channel
has_data = len(y_data) > 0
all_nan = has_data and np.all(np.isnan(y_data))
logger.debug(
    f"Channel {ch}: visible=True, points={len(y_data)}, "
    f"has_data={has_data}, all_nan={all_nan}"
)
```

**What This Does:**
- Logs visibility status for each channel
- Reports number of data points
- Detects if data is all NaN (can happen with low signal)
- Helps diagnose data quality issues

## Expected Behavior After Fix

### Startup Sequence:
1. ✅ UI creates checkboxes (all checked by default)
2. ✅ `setup()` creates SensorgramGraph and SegmentGraph
3. ✅ Signal connections established (checkbox ↔ plot visibility)
4. ✅ **NEW:** Visibility initialization loop runs
5. ✅ Each plot's visibility set to match checkbox state
6. ✅ Channel 'd' plot becomes visible
7. ✅ Data updates will now render channel 'd'

### Debug Output (Expected):
```
DEBUG :: Initialized channel a visibility: True
DEBUG :: Initialized channel b visibility: True
DEBUG :: Initialized channel c visibility: True
DEBUG :: Initialized channel d visibility: True
DEBUG :: Channel a: visible=True, points=42, has_data=True, all_nan=False
DEBUG :: Channel b: visible=True, points=42, has_data=True, all_nan=False
DEBUG :: Channel c: visible=True, points=42, has_data=True, all_nan=False
DEBUG :: Channel d: visible=True, points=42, has_data=True, all_nan=False
```

### If Channel 'd' Still Not Visible:
The debug logs will reveal the actual issue:
- `visible=False` → Checkbox unchecked or initialization failed
- `points=0` → No data being acquired for channel 'd'
- `all_nan=True` → Data acquired but all NaN (signal too low)

## Additional Context

### Bottom Sensorgram Display
**Component:** `SOI_view` (SegmentGraph - "Cycle of Interest")
**Fix Applied:** Same initialization applies to both views
```python
self.full_segment_view.display_channel_changed(ch, is_checked)  # Top graph
self.SOI_view.display_channel_changed(ch, is_checked)           # Bottom graph
```

### Calibration Status
Note: Config file shows `Calibrated: False` and channel 'd' not in LED intensities.
This suggests calibration may not have completed. However, the visibility fix is
independent of calibration status.

## Testing Recommendations

1. **Start the application:**
   ```powershell
   python run_app.py
   ```

2. **Check terminal for initialization logs:**
   Look for: `"Initialized channel d visibility: True"`

3. **Navigate to Sensorgram tab**

4. **Verify channel 'd' appears in both:**
   - Top sensorgram graph (live data)
   - Bottom SOI graph (cycle of interest)

5. **Toggle channel 'd' checkbox:**
   - Uncheck → plot should disappear
   - Check → plot should reappear

6. **Monitor debug logs during live acquisition:**
   Look for: `"Channel d: visible=True, points=X, has_data=True"`

## Files Modified

1. **widgets/datawindow.py**
   - Added visibility initialization loop in `__init__()`
   - Lines 335-342 (after signal connections)

2. **widgets/graphs.py**
   - Added `import numpy as np`
   - Enhanced debug logging in `update()` method
   - Lines 132-147

## Success Criteria

✅ Channel 'd' checkbox visible and checked by default
✅ Channel 'd' plot visible in top sensorgram graph
✅ Channel 'd' plot visible in bottom SOI graph
✅ Debug logs confirm visibility initialization
✅ Debug logs show channel 'd' data being plotted
✅ Toggling checkbox works correctly

## Rollback Instructions

If this fix causes issues, revert the changes:

```bash
git diff widgets/datawindow.py
git diff widgets/graphs.py
git checkout widgets/datawindow.py widgets/graphs.py
```

Or manually remove:
- Lines 335-342 in `widgets/datawindow.py`
- Debug logging additions in `widgets/graphs.py` (lines 141-147)
