# 🔬 Quick Start: Using the Diagnostic Viewer

## What is it?
A **real-time 4-panel viewer** that shows all processing steps as data flows through the SPR acquisition pipeline. No file I/O needed - data streams directly from the hardware!

## How to Open

### Method 1: From Main Application (Recommended)
1. Launch the app: `python run_app.py`
2. Look for the **🔬 microscope button** in the top toolbar (blue highlight)
3. Click it to open the diagnostic viewer window

### Method 2: Standalone Test
```bash
python test_diagnostic_viewer.py
```
This creates simulated data to test the viewer independently.

## What You'll See

The viewer shows **4 live plots** updating in real-time:

```
┌─────────────────────┬─────────────────────┐
│  1. Raw Spectrum    │  3. S-Reference     │
│     (Blue)          │     (Orange)        │
│                     │                     │
│  Raw counts from    │  S-mode reference   │
│  detector           │  signal (corrected) │
├─────────────────────┼─────────────────────┤
│  2. Dark Corrected  │  4. Transmittance   │
│     (Green)         │     (Red)           │
│                     │                     │
│  After dark noise   │  Final P/S ratio    │
│  subtraction        │  (% transmission)   │
└─────────────────────┴─────────────────────┘
```

## Controls

### Top Bar
- **Status**: Shows current channel (A/B/C/D) and pixel count
- **⏸ Pause**: Freezes the display to examine current data
- **▶ Resume**: Continues live updates
- **☑ Highlight SPR Range**: Toggle green shading for 580-720nm region

### Plot Features
- **Statistics**: Each plot shows Mean, Max, Min, Std deviation
- **Auto-scale**: Plots automatically adjust to data range
- **Wavelength axis**: Shows actual wavelengths (nm) on X-axis

## Typical Workflow

### 1. Start Your Experiment
```bash
python run_app.py
```

### 2. Connect & Calibrate
- Wait for hardware to connect
- Complete the calibration sequence
- Calibration takes ~2-3 minutes

### 3. Begin Data Acquisition
- Start your SPR experiment
- Data begins flowing through the system

### 4. Open Diagnostic Viewer
- Click the **🔬 button** in toolbar
- Viewer window opens and starts updating immediately
- All 4 plots refresh in real-time (several times per second)

### 5. Monitor Your Data
- **Watch the raw spectrum** - should show clean signal in 580-720nm range
- **Check dark correction** - should remove baseline
- **Verify S-reference** - should be stable during acquisition
- **Monitor transmittance** - final P/S ratio, should show SPR response

### 6. Pause If Needed
- Click **⏸ Pause** to freeze the display
- Examine specific features in detail
- Click **▶ Resume** to continue

## What to Look For

### ✅ Good Data
- **Raw spectrum**: Smooth curve, 580-720nm range
- **Dark corrected**: Similar shape, lower baseline
- **S-reference**: Stable, consistent across channels
- **Transmittance**: Shows SPR dips/peaks as expected

### ⚠️ Problems to Watch For
- **Noisy raw spectrum**: Check integration time, light levels
- **Negative dark correction**: Dark noise measurement may be wrong
- **Unstable S-reference**: LED or optical alignment issues
- **Flat transmittance**: No SPR signal detected

## Tips

### Performance
- The viewer is lightweight and won't slow down acquisition
- Updates happen in background thread
- Close viewer anytime if you don't need it

### Multiple Channels
- Status shows which channel is currently displayed (A/B/C/D)
- All channels update sequentially
- Data updates several times per second

### Size Mismatches
- The viewer automatically handles size mismatches
- If wavelengths and spectrum differ in length, it trims to minimum
- No crashes from size errors!

## Keyboard Shortcuts
- **Space**: Toggle pause/resume (when viewer window is focused)
- **Esc**: Close viewer window

## Troubleshooting

### Viewer Not Opening?
1. Check that pyqtgraph is installed: `pip install pyqtgraph`
2. Look for error messages in terminal
3. Try standalone test: `python test_diagnostic_viewer.py`

### No Data Showing?
1. Verify acquisition is running (check main window status)
2. Check terminal for "processing_steps_signal" messages
3. Try closing and reopening the viewer

### Plots Look Wrong?
1. Click **☑ Highlight SPR Range** to see if data is in 580-720nm
2. Check the statistics (mean/max/min values)
3. Use **⏸ Pause** to freeze and examine closely

## Advanced Usage

### Compare Before/After Processing
- Pause the viewer at any point
- Compare raw vs final transmittance
- Verify each processing step is working correctly

### Debug Calibration Issues
- Open viewer during calibration
- Watch S-reference and transmittance develop
- Identify problems early in the process

### Verify Bug Fixes
- The viewer clearly shows the wavelength sampling bug was fixed
- Raw spectrum now displays 580-720nm (not 441-580nm)
- All plots show correct wavelength range

## Example Session

```bash
# Terminal 1: Main app
python run_app.py

# Wait for calibration to complete...
# Status shows: "Ready for acquisition"

# Click 🔬 button in toolbar
# Viewer opens with 4 live plots

# During acquisition:
# - All plots update in real-time
# - Wavelength axis shows 580-720nm
# - Statistics update continuously
# - Can pause anytime to examine

# When done:
# - Close viewer window (doesn't stop acquisition)
# - Or leave open for continuous monitoring
```

## Summary

The diagnostic viewer gives you **complete visibility** into your SPR data processing pipeline:

✅ **Real-time** - See data as it's acquired  
✅ **4-step view** - Raw → Dark → S-ref → Transmittance  
✅ **Interactive** - Pause, zoom, examine statistics  
✅ **Integrated** - One click from main toolbar  
✅ **Reliable** - Handles size mismatches automatically  

Perfect for:
- 🔍 Debugging processing issues
- ✅ Verifying calibration quality
- 📊 Monitoring experiment progress
- 🐛 Confirming bug fixes

**Ready to use!** Just click the 🔬 button during acquisition.
