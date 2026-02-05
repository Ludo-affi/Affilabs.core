# Calibration Entry/Exit Flow Analysis - All 5 Types

**Last Updated:** February 3, 2026
**Files Analyzed:**
- [main.py](main.py) (Application class handlers)
- [affilabs/core/calibration_service.py](affilabs/core/calibration_service.py)
- [affilabs/managers/calibration_manager.py](affilabs/managers/calibration_manager.py)
- [affilabs/affilabs_core_ui.py](affilabs/affilabs_core_ui.py)
- [affilabs/core/simple_led_calibration.py](affilabs/core/simple_led_calibration.py)
- [affilabs/core/oem_model_training.py](affilabs/core/oem_model_training.py)

---

## Summary Comparison Table

**UPDATED:** All calibrations now uniformized (Feb 3, 2026)

| Feature | Simple LED | Full Calibration | Polarizer | OEM Calibration | LED Model Training |
|---------|-----------|------------------|-----------|-----------------|-------------------|
| **Stop Live Data** | ✅ Yes (explicit) | ✅ Yes (in service) | ✅ Yes (explicit) | ✅ Yes (in service) | ✅ Yes (explicit) |
| **Confirmation Dialog** | ❌ No | ✅ Yes (checklist) | ❌ No | ✅ Yes (checklist) | ✅ Yes (checklist) |
| **Auto-Start** | ✅ Yes (immediate) | ❌ No (Start button) | ✅ Yes (immediate) | ❌ No (Start button) | ❌ No (Start button) |
| **Progress Dialog** | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes |
| **Can Cancel** | ❌ No | ❌ No (thread daemon) | ✅ Yes (cancel button) | ❌ No (thread daemon) | ❌ No (thread daemon) |
| **Duration** | 10-20 sec | 30-60 sec (no pump)<br>2 min (pump) | 2-5 min | 10-15 min | 2-5 min |
| **Auto-Resume Live** | ✅ Yes (on success) | ✅ Yes (on success) | ✅ Yes (on success) | ✅ Yes (on success) | ✅ Yes (on success) |
| **Clear Graphs** | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes |
| **QC Dialog** | ❌ No | ✅ Yes | ❌ No | ✅ Yes | ❌ No |
| **Success Dialog** | ❌ No (auto-close) | ❌ No (QC dialog) | ✅ Yes | ❌ No (QC dialog) | ✅ Yes |
| **Failure Dialog** | ❌ No (in progress) | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes |

---

## 1. SIMPLE LED CALIBRATION

**Purpose:** Quick LED intensity adjustment for sensor swaps using existing calibration model

**Button Location:** Settings Sidebar → "Simple LED Calibration"

### ENTRY FLOW

**Handler Chain:**
1. Button click → `affilabs_core_ui.py::_handle_simple_led_calibration()`
2. → `calibration_manager.py::handle_simple_led_calibration()`
3. → `main.py::_on_simple_led_calibration()`

**Stops Live Data:** ✅ **YES** - Added explicit stop before calibration

**Confirmation/Dialog:** ❌ **NO** - No confirmation dialog shown

**State Flags Set:**
- None explicitly set
- No `_running` flag check

**UI Elements Disabled:**
- None explicitly disabled
- No button state management

**Pre-Calibration Checks:**
- Hardware connection check (ctrl + usb)
- Stops live data acquisition (prevents hardware conflicts)
- Error dialog if hardware not connected
- No prism/bubble checks

**Dialog Shown:**
```python
StartupCalibProgressDialog(
    title="Simple LED Calibration",
    message="Simple LED Calibration - Quick Intensity Adjustment

    This calibration quickly adjusts LED intensities for sensor swaps:
      • Uses existing LED calibration model
      • Quick S-mode convergence (3-5 iterations)
      • Quick P-mode convergence (3-5 iterations)
      • Updates device config

    Duration: ~10-20 seconds

    Requirements:
      ✓ LED model already exists (run OEM calibration first if needed)
      ✓ Prism installed with water/buffer
      ✓ No air bubbles",
    show_start_button=False  # AUTO-START
)
```

### DURING CALIBRATION

**Process (from [simple_led_calibration.py](affilabs/core/simple_led_calibration.py#L39)):**
1. Load current LED settings from device config
2. Move servo to S position
3. Measure spectrum with current S-mode LEDs
4. Proportionally scale LEDs if outside 40k-55k counts range
5. Verify new S-mode intensity
6. Repeat for P-mode
7. Save adjusted LED values to device config

**Duration:** ~10-20 seconds

**Progress Updates:**
- "Reading current LED settings..." (5%)
- "Measuring S-mode intensity..." (15%)
- "Measuring P-mode intensity..." (50%)
- "Saving adjusted LED values..." (90%)
- "✅ Simple calibration complete!" (100%)

**Cancellation:**
- ❌ **NOT CANCELLABLE** - No cancel button
- Thread is daemon, will terminate on app close

### EXIT FLOW

**On Success:**
- Dialog status: "✅ Simple calibration complete!"
- Progress: 100%
- **Auto-close after 2 seconds** via `dialog.close_from_thread()`
- **Clear graphs and restart sensorgram:**
  ```python
  QTimer.singleShot(0, self._on_clear_graphs_requested)
  ```
- ✅ **Auto-resumes live data** after 100ms delay
- No QC dialog shown
- No success message dialog

**On Failure:**
- Dialog status: "❌ Simple calibration failed" or "❌ Error: {exception}"
- Progress: 100%
- **Auto-close after 2-3 seconds**
- No error dialog shown (error only in progress dialog)
- ❌ **Does NOT clear graphs**
- ❌ **Does NOT resume live data**

**State Flags Reset:**
- None (no state flags used)

---

## 2. FULL CALIBRATION

**Purpose:** Complete 6-step system calibration with convergence and reference capture

**Button Location:** Settings Sidebar → "Full Calibration"

### ENTRY FLOW

**Handler Chain:**
1. Button click → `affilabs_core_ui.py::_handle_full_calibration()`
2. → `calibration_manager.py::handle_full_calibration()`
3. → `main.py::calibration.start_calibration()`
4. → `calibration_service.py::start_calibration(force_oem_retrain=False)`

**Stops Live Data:** ✅ **YES** - Stopped in `calibration_service.py::start_calibration()`:
```python
if self.app.data_mgr._acquiring:
    logger.info("🛑 Stopping live data acquisition before calibration...")
    self.app.data_mgr.stop_acquisition()
    time.sleep(0.1)
```

**Confirmation/Dialog:** ✅ **YES** - Shows pre-calibration checklist dialog

**State Flags Set:**
```python
self._running = False  # Initially False
self._calibration_completed = False
self._current_calibration_data = None
```

**UI Elements Disabled:**
- None explicitly disabled
- Running flag prevents duplicate calibration starts

**Pre-Calibration Checklist Dialog:**
```python
StartupCalibProgressDialog(
    title="Calibrating SPR System",
    message="Please verify before calibrating:

      ✓  Prism installed in sensor holder
      ✓  Water or buffer applied to prism
      ✓  No air bubbles visible
      ✓  Temperature stabilized (10 min after power-on)

    6-Step Calibration Process:
      1. Hardware Validation & LED Verification
      2. Wavelength Calibration
      3. LED Brightness Measurement & 3-Stage Model Load
      4. S-Mode LED Convergence + Reference Capture
      5. P-Mode LED Convergence + Reference + Dark Capture
      6. QC Validation & Result Packaging

    Takes approximately 30-60 seconds.",
    show_start_button=True  # MUST CLICK START
)
```

**Dialog Behavior:**
- Shows checklist immediately
- Progress bar hidden until Start clicked
- **User must click Start button to begin**

### DURING CALIBRATION

**Process (from [calibration_service.py](affilabs/core/calibration_service.py#L387)):**
1. **Hardware validation** - Check ctrl + usb connected
2. **USB buffer clear** - 3 dummy reads to clear old data
3. **Load configuration** - Device-specific config
4. **Run 6-step calibration:**
   - Step 1: Hardware validation & LED verification
   - Step 2: Wavelength calibration
   - Step 3: LED brightness measurement & 3-stage model load
   - Step 4: S-mode LED convergence + reference capture
   - Step 5: P-mode LED convergence + reference + dark capture
   - Step 6: QC validation & result packaging

**Duration:**
- No pump: 30-60 seconds
- With pump: ~2 minutes (includes pump priming in parallel)

**Progress Updates (via `calibration_progress` signal):**
- "Initializing..." (5%)
- "Loading configuration..." (10%)
- "Starting 6-step calibration..." (variable)
- Step-specific progress from calibration_orchestrator
- Final: "✅ Calibration Successful!" (100%)

**Cancellation:**
- ❌ **NOT CANCELLABLE** - No cancel button in dialog
- Thread is daemon

### EXIT FLOW

**On Success:**
1. **Set completion flags:**
   ```python
   self._current_calibration_data = calibration_data
   self._calibration_completed = True
   ```

2. **Emit signal:**
   ```python
   self.calibration_complete.emit(calibration_data)
   ```

3. **Update dialog:**
   - Title: "✅ Calibration Successful!"
   - Status: "🎉 Your system is ready! Review the QC graphs below, then click Start when you're ready to begin live acquisition."
   - Progress: 100%
   - **Enable Start button** (for transition to live view)

4. **Application handler ([main.py](main.py#L1273)):**
   ```python
   _on_calibration_complete_status_update(calibration_data):
       - Set LED intensities from calibration
       - Show QC dialog (modal)
       - Log calibration to database
       - Populate LED brightness in UI
       - Clear graph via graph.clear_plot()
       - Resume live acquisition via acquisition_mgr.start_acquisition()
   ```

5. **QC Dialog shown** - Modal dialog with calibration graphs and metrics

6. ✅ **Auto-resume live data** - Started in `_on_calibration_complete_status_update`

**On Failure:**
1. **Emit signal:**
   ```python
   self.calibration_failed.emit(str(exception))
   ```

2. **Update dialog:**
   - Title: "[ERROR] Calibration Failed"
   - Status: "Error: {error_message}"
   - Progress bar hidden

3. **Error dialog** (via signal handler):
   ```python
   _on_calibration_failed_dialog(error_message)
   ```

4. ❌ **Does NOT clear graphs**
5. ❌ **Does NOT resume live data**

**State Flags Reset:**
```python
finally:
    self._running = False
    logger.info("Calibration service reset - UI should be re-enabled")
```

---

## 3. CALIBRATE POLARIZER (SERVO)

**Purpose:** Servo polarizer calibration to find optimal S and P positions

**Button Location:** Settings Sidebar → "Calibrate Polarizer (Servo)"

### ENTRY FLOW

**Handler Chain:**
1. Button click → `affilabs_core_ui.py::_handle_polarizer_calibration()`
2. → `calibration_manager.py::handle_polarizer_calibration()`
3. → `main.py::_on_polarizer_calibration()`

**Stops Live Data:** ✅ **YES** - Explicitly stopped in handler:
```python
if self.data_mgr._acquiring:
    logger.info("🛑 Stopping live data acquisition before polarizer calibration...")
    self.data_mgr.stop_acquisition()
    time.sleep(0.2)
```

**Confirmation/Dialog:** ❌ **NO** - No pre-calibration confirmation dialog

**State Flags Set:**
- None explicitly set
- No running flag check

**UI Elements Disabled:**
- None explicitly disabled

**Pre-Calibration Checks:**
- Hardware connection check (ctrl + usb)
- Error dialog if hardware not connected

**Progress Dialog:**
```python
QProgressDialog(
    "Initializing polarizer calibration...",
    "Cancel",
    0, 100,
    self.main_window
)
dialog.setWindowTitle("Polarizer Calibration")
dialog.setWindowModality(Qt.WindowModal)
dialog.show()
```

### DURING CALIBRATION

**Process (from servo calibration module):**
1. Import `run_calibration_with_hardware` from servo_polarizer_calibration
2. Run calibration using existing hardware manager
3. Sweep servo positions to find S and P windows
4. Update device config with optimal positions

**Duration:** ~2-5 minutes (depends on polarizer type detection)

**Progress Updates:**
- "Initializing polarizer calibration..." (0%)
- "Running polarizer calibration..." (10%)
- Updates from servo calibration module via callback
- Variable progress based on sweep phase

**Cancellation:**
- ✅ **CAN BE CANCELLED** - Has "Cancel" button
- Check via `progress.wasCanceled()` before each update

### EXIT FLOW

**On Success:**
1. **Close progress dialog:**
   ```python
   progress.close()
   ```

2. **Load new servo positions from device config:**
   ```python
   # Read from device_config.json (hardware section)
   s_position = config["hardware"]["servo_s_position"]
   p_position = config["hardware"]["servo_p_position"]
   ```

3. **Clear graphs and restart sensorgram:**
   ```python
   QTimer.singleShot(0, self._on_clear_graphs_requested)
   ```

4. **Restart live acquisition:**
   ```python
   self.data_mgr.start_acquisition()
   logger.info("✅ Live data acquisition restarted")
   ```

5. **Show success dialog:**
   ```python
   ui_info(
       "Calibration Complete",
       "Polarizer calibration completed successfully!
       Servo moved to P position and live data resumed."
   )
   ```

6. ✅ **Clears graphs** - Fresh start at t=0
7. ✅ **Auto-resume live data**

**On Failure:**
1. **Close progress dialog**

2. **Log error:**
   ```python
   logger.error(f"Polarizer calibration failed: {e}")
   logger.exception("Servo calibration error")
   ```

3. **Show error dialog:**
   ```python
   ui_error(
       "Calibration Failed",
       f"Polarizer calibration encountered an error:\n{str(e)}"
   )
   ```

4. ❌ **Does NOT clear graphs**
5. ❌ **Does NOT resume live data** (must manually restart)

**State Flags Reset:**
- None (no state flags used)

---

## 4. RUN OEM CALIBRATION

**Purpose:** Complete OEM calibration - servo + LED model training + full 6-step calibration (ALWAYS rebuilds optical model)

**Button Location:** Settings Sidebar → "Run OEM Calibration"

### ENTRY FLOW

**Handler Chain:**
1. Button click → Direct connection in [main.py](main.py#L1678):
   ```python
   ui.oem_led_calibration_btn.clicked.connect(self._on_oem_led_calibration)
   ```
2. → `main.py::_on_oem_led_calibration()`

**Stops Live Data:** ✅ **YES** - Stopped in `calibration_service.py` when calibration thread starts

**Confirmation/Dialog:** ✅ **YES** - Shows pre-calibration dialog with Start button

**State Flags Set:**
```python
self.calibration._force_oem_retrain = True  # CRITICAL: Forces model rebuild
self.calibration._running = True
```

**UI Elements Disabled:**
- Start button disabled after click:
  ```python
  dialog.start_button.setEnabled(False)
  ```

**Pre-Calibration Dialog:**
```python
StartupCalibProgressDialog(
    title="OEM Calibration",
    message="OEM Calibration Process:

      STEP 1: Servo Polarizer Calibration
        • Finds optimal S and P positions
        • Takes ~2-5 minutes

      STEP 2: LED Model Training
        • Measures LED response at 10-60ms
        • Creates 3-stage linear model
        • Takes ~2 minutes

      STEP 3: Full 6-Step Calibration
        • LED convergence for S and P modes
        • Reference spectrum capture
        • Takes ~3-5 minutes

    Total time: ~10-15 minutes

    Click Start to begin.",
    show_start_button=True
)
```

**Dialog Behavior:**
- Shows immediately with Start button
- Progress bar hidden
- **User must click Start to begin**
- Start button action:
  ```python
  dialog.hide_start_button()
  dialog.show_progress_bar()
  # Reuse this dialog (don't create new one)
  self.calibration._calibration_dialog = dialog
  # Start calibration thread
  ```

### DURING CALIBRATION

**Process (3 major phases from [calibration_service.py](affilabs/core/calibration_service.py#L387)):**

**Phase 1: Servo Polarizer Calibration (if P4SPR)**
- Detect polarizer type (rotating vs linear)
- Sweep servo positions to find S/P windows
- Save optimal positions to device config
- Duration: 2-5 minutes

**Phase 2: LED Model Training**
- Measure LED response at [10, 20, 30, 45, 60]ms
- Fit 3-stage linear models for each LED
- Save model to `led_calibration_official/spr_calibration/data/`
- Duration: ~2 minutes

**Phase 3: Full 6-Step Calibration**
- Same as Full Calibration flow
- Uses newly trained LED model
- Duration: 30-60 seconds

**Total Duration:** ~10-15 minutes

**Progress Updates:**
- Connected to existing dialog via signal:
  ```python
  self.calibration.calibration_progress.connect(
      lambda msg, prog: dialog.update_status(msg)
  )
  ```
- Step-specific messages from each phase

**Cancellation:**
- ❌ **NOT CANCELLABLE** - No cancel button
- Thread is daemon

### EXIT FLOW

**On Success:**
1. **Same as Full Calibration** - Uses calibration_service completion handler

2. **Application handler triggered:**
   - Set LED intensities
   - Show QC dialog
   - Log to database
   - Clear graph
   - Resume live acquisition

3. ✅ **Auto-resume live data**
4. ✅ **Clear graphs**
5. **QC Dialog shown** with all calibration metrics

**On Failure:**
1. **Same as Full Calibration** - Uses calibration_service failure handler

2. **Dialog updates:**
   - Title: "[ERROR] Calibration Failed"
   - Status: Error message

3. ❌ **Does NOT clear graphs**
4. ❌ **Does NOT resume live data**

**State Flags Reset:**
```python
finally:
    self.calibration._running = False
    self.calibration._force_oem_retrain = False  # Reset retrain flag
```

---

## 5. TRAIN LED MODEL

**Purpose:** LED model training only (no full calibration) - creates 3-stage linear LED model

**Button Location:** Settings Sidebar → "Train LED Model"

### ENTRY FLOW

**Handler Chain:**
1. Button click → Direct connection in [main.py](main.py#L1681):
   ```python
   ui.led_model_training_btn.clicked.connect(self._on_led_model_training)
   ```
2. → `main.py::_on_led_model_training()`

**Stops Live Data:** ✅ **YES** - Stopped explicitly before training

**Confirmation/Dialog:** ✅ **YES** - Shows pre-training dialog with Start button

**State Flags Set:**
- None explicitly (runs in separate thread, not via calibration_service)

**UI Elements Disabled:**
```python
dialog.start_button.setEnabled(False)  # After Start clicked
```

**Pre-Calibration Checks:**
- Hardware connection check (ctrl + usb)
- Stops live data acquisition (prevents spectrum interference)
- Error dialog if hardware not connected

**Pre-Training Dialog:**
```python
StartupCalibProgressDialog(
    title="Training LED Model",
    message="LED Model Training Process:

      1. Servo Polarizer Calibration (if P4SPR)
      2. LED Response Measurement (10-60ms)
      3. 3-Stage Linear Model Fitting
      4. Model File Creation

    This will take approximately 2-5 minutes.

    Click Start to begin.",
    show_start_button=True
)
```

### DURING CALIBRATION

**Process (from [oem_model_training.py](affilabs/core/oem_model_training.py#L397)):**

**Step 1: Servo Polarizer Calibration (if applicable)**
- Only for P4SPR/P4PRO/EZSPR/AFFINITE devices
- Find S and P positions
- Duration: 2-5 minutes

**Step 2: LED Response Measurement**
- Measure dark current at [10, 20, 30, 45, 60]ms
- For each LED (A, B, C, D):
  - Test intensities: [30, 60, 90, 120, 150]
  - Measure spectrum at each integration time
  - Handle saturation (switch to shorter times if needed)

**Step 3: Model Fitting**
- Fit linear models: counts = slope × intensity
- Create 3-stage model for each LED
- Validate model quality

**Step 4: Save Model**
- Save to `led_calibration_official/spr_calibration/data/{detector_serial}_led_model.json`
- Include metadata and model parameters

**Total Duration:** 2-5 minutes

**Progress Updates:**
```python
progress_callback(message: str, percent: int)
dialog.update_status(message)
dialog.set_progress(percent, 100)
```

**Cancellation:**
- ❌ **NOT CANCELLABLE** - No cancel button
- Thread is daemon

### EXIT FLOW

**On Success:**
1. **Update dialog:**
   ```python
   dialog.update_title("LED Model Training Complete")
   dialog.update_status("✓ Model created successfully!")
   dialog.hide_progress_bar()
   ```

2. **Clear graphs and restart sensorgram:**
   ```python
   QTimer.singleShot(0, self._on_clear_graphs_requested)
   ```

3. **Restart live acquisition:**
   ```python
   self.data_mgr.start_acquisition()
   logger.info("✅ Live data acquisition restarted")
   ```

4. **Close dialog and show success:**
   ```python
   QTimer.singleShot(500, lambda: (
       dialog.close(),
       ui_info(
           "Training Complete",
           "LED calibration model created successfully!

           The new model is now active and will be used for all calibrations."
       )
   ))
   ```

5. ✅ **Clears graphs** - Fresh start at t=0
6. ✅ **Auto-resumes live data**

**On Failure:**
1. **Update dialog:**
   ```python
   dialog.update_title("Training Failed")
   dialog.update_status("❌ Model training encountered errors")
   dialog.hide_progress_bar()
   ```

2. **Close dialog and show error:**
   ```python
   QTimer.singleShot(500, lambda: (
       dialog.close(),
       ui_error(
           "Training Failed",
           "LED model training failed.\n\nPlease check the logs for details."
       )
   ))
   ```

3. ❌ **Does NOT clear graphs**
4. ❌ **Does NOT resume live data**

**State Flags Reset:**
- None (independent thread, not via calibration_service)

---

## KEY DIFFERENCES SUMMARY

**UPDATED:** All calibrations now uniformized (Feb 3, 2026)

### Automatic vs Manual Start

**Auto-Start (Immediate):**
- Simple LED Calibration
- Polarizer Calibration

**Manual Start (Requires Button Click):**
- Full Calibration
- OEM Calibration
- LED Model Training

### Live Data Management ✅ UNIFORMIZED

**All Calibrations Now:**
✅ Stop live data before starting
✅ Auto-resume live data on success (after 100ms delay)
✅ Clear graphs before resuming (fresh start at t=0)

### Graph Clearing ✅ UNIFORMIZED

**All Calibrations Now:**
✅ Clear graphs on success
❌ Do NOT clear on failure (preserve error context)

### Post-Calibration Dialogs

**Shows QC Dialog:**
- Full Calibration
- OEM Calibration

**Shows Success Info Dialog:**
- Polarizer Calibration
- LED Model Training

**No Post-Calibration Dialog:**
- Simple LED Calibration (auto-closes)

---

## CRITICAL ISSUES IDENTIFIED

**STATUS: FIXED (Feb 3, 2026)** ✅

All calibrations have been uniformized to follow the standard pattern:
1. Stop live data acquisition
2. Run calibration
3. Clear graphs
4. Restart live data acquisition

### ~~1. Simple LED Calibration~~ ✅ FIXED
~~**Issue:** Does NOT stop live acquisition before calibration~~
~~**Impact:** May cause conflicts with hardware access~~
**RESOLUTION:** Added `stop_acquisition()` before calibration starts

### ~~2. LED Model Training~~ ✅ FIXED
~~**Issue:** Does NOT check if live data is running~~
~~**Impact:** May interfere with spectrum acquisition~~
**RESOLUTION:** Added `stop_acquisition()` before training starts

### ~~3. Simple LED Calibration~~ ✅ FIXED
~~**Issue:** Clears graphs but does NOT resume live data~~
~~**Impact:** User sees empty graph with no data flowing~~
**RESOLUTION:** Added `start_acquisition()` after graph clear

### 4. Polarizer Calibration - Cancellation
**Issue:** Has cancel button but unclear if cancellation is clean
**Impact:** May leave servo in intermediate position
**Location:** [main.py](main.py#L7646)
**Verification Needed:** Test cancel behavior thoroughly

---

## RECOMMENDATIONS

### ✅ Completed Standardization (Feb 3, 2026)

1. **✅ Unified Live Data Management:**
   - All calibrations now stop live data on entry
   - All calibrations now resume live data on success
   - Consistent pattern applied across all calibration types

2. **✅ Graph Clearing Uniformized:**
   - All calibrations now clear graphs on success
   - Fresh start at t=0 after every calibration
   - Error context preserved on failure

### Remaining Improvement Opportunities

1. **Progress Dialog Consistency:**
   - Consider standardizing Polarizer Calibration to use `StartupCalibProgressDialog`
   - Currently uses `QProgressDialog` (inconsistent with others)

2. **State Flag Management:**
   - Consider adding `_running` flag to Simple LED and Polarizer
   - Would prevent duplicate calibration starts

3. **Error Handling:**
   - Consider showing modal error dialogs for all failures
   - Simple LED only shows error in progress dialog (less visible)

4. **Cancellation Support:**
   - Consider adding cancel support to all calibrations
   - Currently only Polarizer has cancel button
   - Risk: May leave hardware in intermediate state

### Documentation Needs

1. **User Guide:** Document expected duration for each calibration type
2. **Developer Guide:** Document unified calibration pattern
3. **Testing Guide:** Add test cases for live data management
