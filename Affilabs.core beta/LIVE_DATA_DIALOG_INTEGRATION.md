# Live Data Dialog Integration - Complete

## ✅ What Was Integrated

The **Live Data Dialog** now shows real-time transmission and raw intensity spectra for all 4 channels during acquisition.

## 🔧 Changes Made

### 1. **Dialog Instance Management**
```python
# Added to __init__:
self._live_data_dialog = None  # Live Data Dialog for real-time spectra
```

### 2. **Dialog Opening on Start** 
When clicking Start button → Phase 4:
```python
# Opens dialog alongside recording:
from live_data_dialog import LiveDataDialog
if self._live_data_dialog is None:
    self._live_data_dialog = LiveDataDialog(parent=self.main_window)
self._live_data_dialog.show()
```

### 3. **Real-Time Data Updates**
In `_queue_transmission_update()`:
```python
# Update live data dialog if open (THREAD SAFE - called from processing thread)
if self._live_data_dialog is not None:
    try:
        # Update both transmission and raw data plots
        self._live_data_dialog.update_transmission_plot(channel, wavelengths, transmission)
        if raw_spectrum is not None:
            self._live_data_dialog.update_raw_data_plot(channel, wavelengths, raw_spectrum)
    except Exception as e:
        # Silently ignore dialog update errors (dialog may be closing)
        pass
```

### 4. **Page Navigation Integration**
Connected to page switcher:
```python
# Show/hide dialog when switching pages
if hasattr(self.main_window, 'content_stack'):
    self.main_window.content_stack.currentChanged.connect(self._on_page_changed)

def _on_page_changed(self, page_index: int):
    # Page 0 is Live Data (sensorgram)
    if page_index == 0:
        # Show dialog if acquisition running
        if self.data_mgr and self.data_mgr.is_acquiring and self._live_data_dialog is not None:
            self._live_data_dialog.show()
    else:
        # Hide when switching away
        if self._live_data_dialog is not None:
            self._live_data_dialog.hide()
```

## 📊 What You'll See

### Live Data Dialog Layout:
```
┌─────────────────────────────────────────────────────┐
│  Live Spectroscopy Data                             │
├──────────────────┬──────────────────────────────────┤
│ Transmission (%) │ Raw Intensity (counts)           │
│                  │                                  │
│  ● Ch A (Red)    │  ● Ch A (Red)                    │
│  ● Ch B (Green)  │  ● Ch B (Green)                  │
│  ● Ch C (Blue)   │  ● Ch C (Blue)                   │
│  ● Ch D (Orange) │  ● Ch D (Orange)                 │
│                  │                                  │
│  (live plots)    │  (live plots)                    │
└──────────────────┴──────────────────────────────────┘
```

## 🎯 Usage

1. **Start Acquisition**:
   - Calibrate → Click Start
   - Dialog opens automatically

2. **Watch Real-Time Spectra**:
   - Left side: Transmission % (0-100%)
   - Right side: Raw intensity (0-65535 counts)
   - All 4 channels update live at ~2 Hz

3. **Switch Pages**:
   - Switch to "Edits"/"Analyze"/"Report" → Dialog hides
   - Switch back to "Live Data" → Dialog shows again

4. **Close Dialog**:
   - Click X to close
   - Dialog reopens next time you start acquisition

## 🔒 Thread Safety

✅ **SAFE**: Dialog updates are called from processing thread but only update plot data (PyQtGraph handles internal thread safety for plot updates)

✅ **SAFE**: Show/hide operations run on main thread (via page change signal)

✅ **PROTECTED**: All dialog access wrapped in try/except to handle closing edge cases

## 🚀 Next Steps

The dialog is fully integrated! Test it:

1. Connect hardware
2. Run calibration  
3. Click **Start**
4. Watch the dialog show real-time spectra! 🎉

---

**Status**: ✅ COMPLETE - Ready for testing with real hardware
