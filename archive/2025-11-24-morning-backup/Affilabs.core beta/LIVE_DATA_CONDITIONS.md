# Live Data Reading Conditions

## Overview
The system has multiple layers that control when live data is acquired and displayed.

---

## 1. Data Acquisition Layer (Backend)

### Start Conditions (`data_acquisition_manager.py`)

**`start_acquisition()` will START if:**
- ✅ System is calibrated (`self.calibrated == True`)
- ✅ Hardware is connected (`_check_hardware()` passes)
- ✅ Not already acquiring (`self._acquiring == False`)

**`start_acquisition()` will FAIL if:**
- ❌ Not calibrated → Shows: "Calibrate before starting acquisition"
- ❌ Hardware not connected → Shows: "Hardware not connected"
- ⚠️ Already running → Just logs warning, doesn't emit error

### Automatic Start Triggers

**After hardware connection (`_on_hardware_connected()`):**
1. If controller + spectrometer detected → Auto-start calibration
2. If only spectrometer detected → Auto-start acquisition (no calibration)
3. If no spectrometer → No acquisition started

**After successful calibration (`_on_calibration_complete()`):**
- Always auto-starts acquisition: `self.data_mgr.start_acquisition()`

### Stop Conditions

**`stop_acquisition()` is called:**
- User powers off hardware
- Hardware disconnects unexpectedly
- Manual stop requested (though no UI button for this currently)

---

## 2. Live Data Display Layer (UI)

### Display Control (`main_window.live_data_enabled`)

**Default State:**
- `live_data_enabled = True` (enabled by default)

**User Toggle:**
- Checkbox in Graphic Control tab: "Live Data Updates"
- Allows freezing graphs while data continues to be acquired in background

**What it controls:**

```python
# Transmission/raw spectrum plots (updated per channel)
if self.main_window.live_data_enabled and hasattr(self.main_window, 'transmission_curves'):
    # Update transmission curve
    # Update raw data curve

# Timeline graph (updated per data point)
if self.main_window.live_data_enabled:
    # Update full timeline graph
    # Update zoomed region graph
```

**Important:**
- When `live_data_enabled = False`:
  - Data is still acquired and processed in background
  - Data is still buffered and can be exported
  - Only the graph updates are paused
  - Graphs remain frozen at last displayed state

---

## 3. Complete Flow Diagram

```
Power On Button Clicked
    ↓
Hardware Manager: scan_hardware()
    ↓
Hardware Connected Signal
    ↓
┌─────────────────────────────────────────┐
│ Check: Controller + Spectrometer?       │
├─────────────────────────────────────────┤
│ YES → Start Calibration                 │
│   ↓                                     │
│   Calibration Worker (background)       │
│   ↓                                     │
│   ┌─ Integration Time (10-100ms)       │
│   ├─ S-mode LED Calibration            │
│   ├─ Dark Noise Measurement            │
│   ├─ S-ref Capture                     │
│   ├─ P-mode LED Calibration            │
│   └─ Verification                      │
│   ↓                                     │
│   Calibration Complete Signal          │
│   ↓                                     │
│   Auto-start Acquisition ─────────────┐│
│                                        ││
│ NO (Spectrometer only) ────────────────┘│
│   Skip calibration                     ││
│   Start Acquisition directly           ││
└────────────────────────────────────────┘│
                                          ↓
                            ┌─────────────────────────────┐
                            │ Acquisition Loop (thread)    │
                            │ - Read all 4 channels        │
                            │ - Calculate transmission     │
                            │ - Emit data signals          │
                            │ - Batch processing (50/sec)  │
                            └─────────────────────────────┘
                                          ↓
                            ┌─────────────────────────────┐
                            │ UI Data Handler              │
                            │ if live_data_enabled:        │
                            │   - Update transmission plot │
                            │   - Update raw data plot     │
                            │   - Update timeline graph    │
                            │   - Update zoomed region     │
                            └─────────────────────────────┘
```

---

## 4. Current Issues & Observations

### Calibration Boundary Handling (FIXED)

**Previous Issue:**
- Calibration would completely fail if ANY channel failed
- `if not cal_result.success:` → Exception raised
- All partial successes treated as complete failures

**Fix Applied:**
```python
# Now checks for critical failure only
if cal_result.integration_time is None or cal_result.integration_time == 0:
    raise Exception("Critical calibration failure")

# Partial failures are logged but allowed
if len(cal_result.ch_error_list) > 0:
    logger.warning(f"Partial calibration: {len(cal_result.ch_error_list)} channel(s) failed")
```

**Result:**
- ✅ Calibration succeeds if at least integration time is determined
- ✅ Failed channels are tracked in `ch_error_list`
- ✅ UI shows warning for failed channels but allows usage
- ✅ System continues with working channels

### Live Data vs Acquisition

**Key Distinction:**
1. **Data Acquisition** (Backend):
   - Controlled by `start_acquisition()` / `stop_acquisition()`
   - Hardware-level reading of spectra
   - Always runs after calibration (if hardware connected)
   - Cannot be paused without stopping acquisition

2. **Live Data Display** (Frontend):
   - Controlled by `live_data_enabled` checkbox
   - UI-level graph updates
   - Can be toggled without affecting acquisition
   - Data continues to buffer when disabled

---

## 5. Potential Improvements

### Missing Features:
1. **Manual acquisition control**
   - No UI button to manually start/stop acquisition
   - Only automatic via calibration completion

2. **Acquisition status indicator**
   - No clear indication of acquisition state in UI
   - Could add indicator showing: "Acquiring" / "Stopped" / "Paused"

3. **Live data pause reason**
   - When `live_data_enabled = False`, user may not realize data still buffers
   - Could show message: "Graph frozen - data still recording"

4. **Calibration partial success clarity**
   - Warning message shows failed channels
   - Could be more explicit about which channels are usable

---

## 6. Debug Checklist

**If live data is not updating:**

1. ☑️ Check acquisition status: `self.data_mgr._acquiring`
2. ☑️ Check calibration status: `self.data_mgr.calibrated`
3. ☑️ Check live data toggle: `self.main_window.live_data_enabled`
4. ☑️ Check hardware connection: `self.hardware_mgr.get_hardware_status()`
5. ☑️ Check for acquisition errors in logs
6. ☑️ Check channel error list: `self.data_mgr.ch_error_list`
7. ☑️ Verify polarizer mode: Should be 'P' during live acquisition

**Expected log sequence:**
```
INFO :: Starting automatic calibration...
INFO :: Starting LED calibration...
INFO :: ✅ Calibration complete - all channels OK
INFO :: 🚀 Starting data acquisition after calibration...
INFO :: 🔄 Switching polarizer to P-mode...
INFO :: ✅ Polarizer in P-mode
INFO :: Starting spectrum acquisition...
INFO :: Acquisition worker started with batch_size=50
```
