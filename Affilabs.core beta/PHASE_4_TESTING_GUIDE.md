# Phase 4: Full Acquisition + Recording + Simulation Testing

## Overview

Phase 4 adds **recording functionality** to the data acquisition pipeline and includes **simulation mode** to test the complete data flow without hardware.

---

## What's New in Phase 4

### 1. Recording Manager Integration
```python
# Phase 4 adds one line to Start button:
self.recording_mgr.start_recording()
```

**Complete Flow:**
1. Hardware validation ✅
2. Hardware configuration (polarizer, integration, LEDs) ✅
3. Data acquisition thread started ✅
4. **Recording started** ⭐ NEW
5. UI updates ✅

### 2. Simulation Mode
Test the complete pipeline with fake data - **no hardware required!**

---

## Testing Phase 4

### Method 1: Manual Testing with Hardware
1. Run the app: `python main_simplified.py`
2. Press **Ctrl+Shift+C** to bypass calibration
3. Click **Start** button
4. Watch for crashes during acquisition + recording
5. Check that data files are created in the output directory

### Method 2: Simulation Mode (No Hardware)
1. Run the app: `python main_simplified.py`
2. Press **Ctrl+Shift+C** to bypass calibration (injects fake cal data)
3. Click **Start** button to start acquisition + recording
4. Press **Ctrl+Shift+S** to inject simulated spectra
5. Watch the live data graph update with fake SPR curves
6. Check logs for any pipeline errors

**Simulation generates:**
- 4 channels (A, B, C, D) with realistic SPR peaks
- Wavelength range: 200-1100nm (3648 pixels)
- Gaussian peaks at different wavelengths (650-670nm)
- Random noise + baseline
- 10 Hz data rate (100ms interval)

---

## Keyboard Shortcuts

| Shortcut | Action | Description |
|----------|--------|-------------|
| **Ctrl+Shift+C** | Bypass Calibration | Inject fake calibration, enable Start button |
| **Ctrl+Shift+S** | Start Simulation | Inject fake spectra at 10 Hz continuously |

---

## Expected Behavior

### Success Indicators ✅
- **Phase 4 completion dialog** appears
- **No crashes** during acquisition
- **Live data graph updates** with spectra
- **Log shows:** "✅ Recording started successfully"
- **Data files created** in output directory
- **No threading errors** in console

### Failure Indicators ❌
- Application crashes when clicking Start
- No data files created
- Graph doesn't update
- Threading errors in console
- Recording manager errors

---

## Simulation Testing Strategy

### Quick Test (30 seconds)
```bash
# In the running app:
1. Ctrl+Shift+C  (bypass calibration)
2. Click Start    (start acquisition + recording)
3. Ctrl+Shift+S  (inject fake spectra)
4. Wait 30 seconds
5. Check for crashes/errors
```

### Full Stress Test
1. Run simulation for **5-10 minutes**
2. Monitor memory usage
3. Check log file for errors
4. Verify data files are being written
5. Ensure graph stays responsive

---

## What Gets Tested

### Complete Data Pipeline
```
Simulated Spectra Generation
  ↓
data_mgr.spectrum_acquired signal
  ↓
Data Processing (baseline, normalization, derivatives)
  ↓
recording_mgr (save to files)
  ↓
Live Data Graph (UI updates)
  ↓
Export capabilities
```

### Threading Safety
- **Worker thread:** Data acquisition runs in background
- **Qt signals:** Cross-thread communication
- **UI updates:** Graph rendering on main thread
- **File I/O:** Recording to disk

### Memory Management
- Continuous spectrum processing
- Array allocations/deallocations
- Qt object lifecycle
- File handle management

---

## Troubleshooting

### "No spectrum_acquired signal"
**Fix:** Check that `data_mgr` has the signal defined:
```python
self.data_mgr.spectrum_acquired  # Should exist
```

### "Recording manager not found"
**Fix:** Check initialization in `main_simplified.py`:
```python
self.recording_mgr = RecordingManager(...)
```

### Simulation spectra not appearing
**Fix:**
1. Ensure Start button was clicked first (acquisition must be running)
2. Check live data dialog is open
3. Verify `Ctrl+Shift+S` shortcut is registered

### Application still crashes
**If crash happens:**
1. Note EXACTLY when it crashes (which phase?)
2. Check console for last log messages
3. Look for threading errors
4. Try without simulation (hardware only)
5. Try simulation only (no real hardware commands)

---

## Next Steps After Phase 4

### If Phase 4 Works ✅
**Great!** The crash was likely in a specific component we haven't tested yet:
- Kinetic mode operations
- Flow control
- Specific calibration steps
- Pump/valve operations

### If Phase 4 Crashes ❌
**We found it!** The crash is in:
- Data acquisition thread
- Recording pipeline
- Qt signal routing
- Memory management

---

## Files Modified

1. **`main_simplified.py`**
   - Added `self.recording_mgr.start_recording()` in `_on_start_button_clicked()`
   - Registered Ctrl+Shift+S shortcut
   - Updated log messages to "Phase 4"

2. **`quick_sim_test.py`** (NEW)
   - Generates fake SPR spectra
   - Injects via `spectrum_acquired` signal
   - 10 Hz continuous mode

3. **`PHASE_4_TESTING_GUIDE.md`** (THIS FILE)
   - Complete testing documentation

---

## Quick Reference

```python
# Generate one fake spectrum
from quick_sim_test import generate_fake_spectrum
spectrum = generate_fake_spectrum()

# Inject into pipeline
app.data_mgr.spectrum_acquired.emit(spectrum)

# Start continuous injection (Ctrl+Shift+S does this)
from quick_sim_test import setup_simulation_shortcut
setup_simulation_shortcut(app)
```

---

## Log Messages to Watch For

**Success:**
```
🚀 PHASE 4: Full acquisition + recording
🔧 PHASE 2: Configuring hardware...
   ✅ Polarizer configured
   ✅ Integration time configured
   ✅ LED intensities configured
🚀 PHASE 3: Starting data acquisition thread...
   ✅ Data acquisition thread started successfully
🚀 PHASE 4: Starting recording...
   ✅ Recording started successfully
✅ PHASE 4 COMPLETE - Acquisition + Recording running!
📡 Injecting simulated spectra...  (if using Ctrl+Shift+S)
```

**Failure:**
```
❌ Failed to start acquisition: [error]
❌ Failed to start recording: [error]
❌ Simulation error: [error]
```

---

## Summary

Phase 4 = **Phase 3 + Recording + Simulation Testing**

**Goal:** Verify the complete data pipeline works without crashes:
- Acquisition thread ✅
- Data processing ✅
- Recording to files ✅
- UI updates ✅
- Memory management ✅

**Success Criteria:**
- Can run simulation for 5+ minutes without crash
- Data files are created and valid
- Graph updates smoothly
- No threading errors in logs

---

**Ready to test?**
1. Press `Ctrl+Shift+C` to bypass calibration
2. Click **Start**
3. Press `Ctrl+Shift+S` to inject fake data
4. Watch for crashes! 🔍
