# Baseline Data Recording Feature - Implementation Complete

## 🎯 Feature Overview

Added a "Record 5-Min Baseline Data" button in the Settings tab under the Transmission graph. This feature records raw transmission spectra for offline signal processing optimization analysis.

## 📍 Location

**Settings Tab → Live Spectroscopy Section**
- Button appears directly below the Transmission Spectrum graph
- Bright red/orange styling for visibility
- Shows real-time recording progress

## 🔧 Implementation Details

### Files Modified

1. **`src/sidebar_tabs/settings_builder.py`** (lines 614-643)
   - Added red "🔴 Record 5-Min Baseline Data" button after transmission plot
   - Button includes tooltip with usage instructions
   - Styled with gradient background (red when idle, orange when recording)

2. **`src/affilabs_core_ui.py`** (4 locations)
   - **Line ~146**: Imported `BaselineDataRecorder` module
   - **Line ~1722**: Forwarded button reference from sidebar
   - **Line ~6205**: Connected button click signal to handler
   - **Lines ~6148-6290**: Added handler methods for recording control and progress

### Files Created

3. **`src/utils/baseline_data_recorder.py`** (NEW - 300 lines)
   - Complete baseline data recording system
   - Collects transmission spectra + processed wavelengths
   - Real-time progress tracking
   - Automatic file saving with timestamps
   - Comprehensive metadata capture

## 📊 What Gets Recorded

### Data Files (saved to `baseline_data/` directory)

1. **Per-Channel Transmission Spectra** (4 CSV files)
   - `baseline_transmission_ch{a,b,c,d}_YYYYMMDD_HHMMSS.csv`
   - Format: Rows = wavelength points, Columns = time points
   - Contains raw transmission % values for each spectrum

2. **Wavelength Traces** (1 CSV file)
   - `baseline_wavelengths_YYYYMMDD_HHMMSS.csv`
   - Format: Columns for each channel's peak wavelength + timestamps
   - Ready for noise analysis (peak-to-peak variation)

3. **Metadata** (1 CSV file)
   - `baseline_metadata_YYYYMMDD_HHMMSS.csv`
   - Includes: integration time, LED intensities, calibration params
   - Recording duration and timestamp

### Data Collection Rate

- **Expected**: ~1-1.5 Hz per channel (depending on integration time)
- **5 minutes**: ~300-450 spectra per channel
- **File size estimate**:
  - Transmission spectra: ~25 MB total (all channels)
  - Wavelength traces: ~16 KB
  - Metadata: <1 KB

## 🎨 User Experience

### Button States

**Idle State** (Red):
```
🔴 Record 5-Min Baseline Data
```

**Recording State** (Orange with progress):
```
⏹️ Recording... 42% (174s)
```

**Complete**:
- Returns to idle state
- Shows success dialog with file path
- User can send files for analysis

### User Workflow

1. **Start Live Acquisition**
   - Ensure stable baseline (no sample injections)

2. **Click Button**
   - Confirmation dialog appears
   - Warning to keep baseline stable

3. **Recording Progress**
   - Button shows real-time progress percentage
   - Remaining time countdown
   - Can stop early by clicking button again

4. **Completion**
   - Success dialog with file locations
   - Data ready for offline analysis

## 🔬 Data Analysis Workflow

### For You (Offline Analysis)

Once user sends the recorded files, you can:

1. **Load transmission spectra**
   ```python
   import pandas as pd
   import numpy as np

   # Load channel A transmission spectra
   df = pd.read_csv('baseline_transmission_cha_20251126_143022.csv', index_col=0)
   wavelengths = df.index.values
   spectra = df.values  # Shape: (2048 wavelengths, ~400 time points)
   ```

2. **Test different SG filter parameters**
   ```python
   from scipy.signal import savgol_filter

   # Test various window sizes
   for window in [11, 15, 21, 25, 31]:
       for poly in [2, 3, 4]:
           filtered_spectra = savgol_filter(spectra, window, poly, axis=0)
           # Run Fourier peak finding on each spectrum
           # Calculate peak-to-peak noise...
   ```

3. **Test Fourier alpha values**
   ```python
   # For each parameter combination, calculate:
   - Peak-to-peak wavelength variation
   - Standard deviation
   - Processing time
   ```

4. **Grid search optimization**
   ```python
   results = []
   for sg_win in [11, 15, 21, 25, 31]:
       for alpha in [500, 1000, 2000, 5000, 10000]:
           noise = calculate_baseline_noise(...)
           results.append({'sg_window': sg_win, 'alpha': alpha, 'noise': noise})

   # Find optimal parameters
   optimal = min(results, key=lambda x: x['noise'])
   ```

5. **Return optimal settings**
   - Provide exact values for settings.py
   - Include comparison plots showing improvement

## 🚀 Next Steps

### Immediate Testing

1. **Verify button appears**
   - Start application
   - Navigate to Settings tab
   - Scroll to Live Spectroscopy section
   - Button should be visible below transmission graph

2. **Test recording**
   - Complete calibration
   - Start live acquisition
   - Click "Record 5-Min Baseline Data"
   - Confirm dialog
   - Wait 5 minutes (or stop early to test)
   - Check `baseline_data/` directory for files

### Data Analysis (When You're Ready)

1. User records 5-minute baseline
2. User sends you the CSV files
3. You run grid search optimization offline
4. You provide optimal parameters:
   ```python
   # Optimal settings for settings.py
   SG_WINDOW_LENGTH = 27  # Example result
   SG_POLYORDER = 3
   FOURIER_ALPHA = 3500
   FOURIER_WINDOW_SIZE = 165
   ```
5. User updates settings, sees improved baseline noise

## ⚠️ Important Notes

### Dependencies
- **pandas**: Required for CSV export (add to requirements.txt if missing)
  ```
  pip install pandas
  ```

### Error Handling
- **Not calibrated**: Shows error message, button disabled
- **Not in live mode**: Shows error message
- **Already recording**: Stops current recording
- **Save failure**: Shows error dialog with details

### Performance
- **Minimal overhead**: Data collection happens passively via signals
- **Non-blocking**: Recording runs in background
- **Thread-safe**: Uses Qt signals for cross-thread communication

## 📝 Code Quality

### Features Implemented
✅ Real-time progress tracking with countdown timer
✅ Comprehensive error handling with user-friendly messages
✅ Proper signal/slot architecture (Qt best practices)
✅ Automatic timestamped file naming
✅ Complete metadata capture for reproducibility
✅ Clean separation of concerns (recorder module vs UI)
✅ Proper resource cleanup on stop/error

### Style Consistency
✅ Matches existing UI design language
✅ Uses same button styling as other critical actions
✅ Follows Qt/PySide6 best practices
✅ Comprehensive logging for debugging
✅ Type hints throughout

## 🎉 Feature Complete!

The baseline recording feature is now fully integrated and ready for testing. User can record data immediately, and you can analyze it offline to optimize the signal processing pipeline parameters.
