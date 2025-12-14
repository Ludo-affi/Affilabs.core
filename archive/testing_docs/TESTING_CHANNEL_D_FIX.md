# Testing the Channel 'd' Visibility Fix

## What Was Fixed

The sensorgram graphs (both top and bottom) were not initializing plot visibility to match the checkbox state. This caused channel 'd' plots to be hidden even though the checkbox was checked.

**Fix Applied:**
- Added visibility initialization in `widgets/datawindow.py`
- All channel checkboxes now properly control plot visibility from startup
- Enhanced debug logging to diagnose data issues

## How to Test

### 1. Start the Application
```powershell
python run_app.py
```

### 2. Complete Calibration
- Wait for calibration to finish (all 8 steps)
- You should see "✅ Calibration complete" message

### 3. Navigate to Sensorgram Tab
- Click on the "Sensorgram" tab in the main window
- This tab should show:
  - **Top graph**: Live sensorgram data for all channels
  - **Bottom graph**: Cycle of Interest (SOI) display

### 4. What to Look For

**Terminal Output:**
When the sensorgram tab first opens, you should see:
```
INFO :: ✅ Initialized channel a visibility: True
INFO :: ✅ Initialized channel b visibility: True
INFO :: ✅ Initialized channel c visibility: True
INFO :: ✅ Initialized channel d visibility: True
```

**GUI Display:**
- **All 4 channel checkboxes** (A, B, C, D) should be **checked** ✅
- **All 4 colored lines** should appear in the top sensorgram graph:
  - Channel A: **Black**
  - Channel B: **Red**
  - Channel C: **Blue**
  - Channel D: **Green** ← This was missing before!

### 5. Start Live Mode
- Click "Live" button to start data acquisition
- Watch all 4 channels update in real-time
- Channel 'd' (green line) should now be visible!

### 6. Toggle Channel Visibility
Test that the checkbox controls work:
- **Uncheck** channel D checkbox → green line disappears
- **Check** channel D checkbox → green line reappears

## If Channel 'd' Still Doesn't Appear

### Check 1: Is the Plot Visible?
Look for debug logs like:
```
DEBUG :: Skipping hidden channel d (plot not visible)
```
If you see this, the visibility initialization didn't work.

### Check 2: Is There Data?
Look for logs like:
```
DEBUG :: Channel d: visible=True, points=0, has_data=False
```
If `points=0`, no data is being acquired for channel 'd'.

### Check 3: Is Data All NaN?
Look for logs like:
```
DEBUG :: Channel d: visible=True, points=42, has_data=True, all_nan=True
```
If `all_nan=True`, the channel has low signal (related to calibration warning you saw).

## Calibration Warning Seen Earlier

```
⚠️  Channel d: Signal low (57.4%), Step 6 will adjust
```

This suggests channel 'd' has lower signal than expected. Possible causes:
1. **LED intensity too low** for that channel
2. **Optical path issue** (alignment, fiber coupling)
3. **Detector sensitivity** variation
4. **Sample/prism** affecting that wavelength range differently

The calibration should have compensated for this, but if signal is extremely low, you might see all NaN values in the data.

## Expected Behavior After Fix

### Before Fix:
- ❌ Channel 'd' checkbox: Checked but plot not visible
- ❌ Only channels A, B, C showing in graphs
- ❌ No initialization logs

### After Fix:
- ✅ Channel 'd' checkbox: Checked AND plot visible
- ✅ All 4 channels (A, B, C, D) showing in graphs
- ✅ Initialization logs confirm visibility set correctly
- ✅ Toggling checkbox properly shows/hides plot

## Troubleshooting

### If initialization logs don't appear:
1. The sensorgram tab might not have been created yet
2. Try clicking on different tabs and back to Sensorgram
3. Check if logger is filtering INFO level logs

### If channel 'd' has no data points:
1. Check if channel 'd' is in the active channels list
2. Verify calibration completed successfully for channel 'd'
3. Check LED intensity for channel 'd' is not zero

### If channel 'd' data is all NaN:
1. Signal too low during calibration
2. Re-run calibration with better sample/conditions
3. Check hardware (LED, optical path, detector)

## Files Modified

1. `widgets/datawindow.py` - Added visibility initialization (lines 335-342)
2. `widgets/graphs.py` - Added numpy import and enhanced debug logging

## Next Steps

If the fix works:
- ✅ Document the fix in SUCCESS_SUMMARY.md
- ✅ Consider adding auto-recovery for low signal channels
- ✅ Test with different calibration conditions

If the fix doesn't work:
- 📋 Collect debug logs showing actual visibility state
- 📋 Check if DataWindow is created at different time
- 📋 Verify checkbox→plot signal connections work
