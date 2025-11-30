# QC Dialog to Live Data Audit

## Current Behavior Analysis

### ✅ What Works
1. **Calibration completes** → `calibration_complete.emit()`
2. **Signal received** by `_on_calibration_complete()` (main_simplified.py:528)
3. **Calibration applied** to data_mgr
4. **QC Dialog shows** with calibration results
5. **Dialog is non-modal** (doesn't block UI)

### ❌ The Problem: No Clear Path from QC Dialog to Live Data

**Issue**: QC dialog only has a "Close" button. After closing it, users must:
1. Look for the Start button in the main window sidebar
2. Click it manually to begin live acquisition

**User Experience Problem**: Not intuitive - users expect a workflow like:
```
Calibration → QC Review → Click "Start Live Data" → Acquisition begins
```

**Current Reality**:
```
Calibration → QC Review → Close dialog → Find Start button → Click it → Acquisition begins
              ↑
      Disconnected here!
```

---

## Architecture Analysis

### Flow Diagram

```
CalibrationService
  ├─ _run_calibration() [Thread]
  │   └─ run_full_6step_calibration()
  │       └─ Returns LEDCalibrationResult
  │
  ├─ calibration_complete.emit(calibration_data)
  │
  └─ [Progress Dialog has Start button]
      └─ After calibration: Start button becomes "Start Live Data"
          └─ _on_start_button_clicked() → data_mgr.start_acquisition()

main_simplified.py
  ├─ _on_calibration_complete(calibration_data)
  │   ├─ data_mgr.apply_calibration()
  │   └─ _show_qc_dialog()
  │       └─ Shows CalibrationQCDialog [ONLY HAS "CLOSE" BUTTON]
  │
  └─ User must manually click Start button in sidebar
```

### Issue Identified

**CalibrationService Progress Dialog** has the logic:
- Line 158: `_on_start_button_clicked()`
- Line 159: If `_calibration_completed` → start live acquisition
- Line 185: `self.app.data_mgr.start_acquisition()`

**But**: This dialog is CLOSED before QC dialog is shown!

---

## Root Cause

### Timeline of Events:

1. **Calibration starts** → Progress dialog shows with "Start" button
2. **User clicks "Start"** → Calibration begins
3. **Calibration completes** → `calibration_complete.emit()`
4. **Signal handler runs**:
   - `_on_calibration_complete()` applies calibration
   - `_show_qc_dialog()` shows QC dialog
5. **Progress dialog**: Still open but hidden behind QC dialog
6. **User**: Looking at QC dialog, sees only "Close" button
7. **Expected**: Click something to start live data
8. **Reality**: Must close QC dialog, find Start button in sidebar

---

## Solutions

### Option 1: Add "Start Live Data" Button to QC Dialog ⭐ RECOMMENDED

**Implementation**:
```python
# In CalibrationQCDialog._setup_ui() (line ~125)

# Button layout with both Close and Start
button_layout = QHBoxLayout()
button_layout.addStretch()

close_btn = QPushButton("Close")
close_btn.clicked.connect(self.accept)
button_layout.addWidget(close_btn)

# ADD THIS:
start_btn = QPushButton("✅ Start Live Data")
start_btn.setStyleSheet("""
    QPushButton {
        background: #34C759;  /* Green */
        color: white;
        font-weight: 600;
        min-width: 150px;
    }
    QPushButton:hover {
        background: #30B350;
    }
""")
start_btn.clicked.connect(self._on_start_live_clicked)
button_layout.addWidget(start_btn)

layout.addLayout(button_layout)
```

**Add signal and handler**:
```python
# In CalibrationQCDialog class:
from PySide6.QtCore import Signal

class CalibrationQCDialog(QDialog):
    # Add signal
    start_live_requested = Signal()

    def _on_start_live_clicked(self):
        """User clicked Start Live Data button."""
        logger.info("🚀 User clicked Start Live Data from QC dialog")
        self.start_live_requested.emit()
        self.accept()  # Close dialog
```

**Connect in main_simplified.py**:
```python
# In _show_qc_dialog() (line ~589)
self._qc_dialog = CalibrationQCDialog.show_qc_report(
    parent=self.main_window,
    calibration_data=qc_data
)

# ADD THIS:
self._qc_dialog.start_live_requested.connect(self._on_start_button_clicked)
logger.info("Connected: QC dialog start_live_requested -> _on_start_button_clicked")
```

**Benefits**:
- ✅ Clear user workflow
- ✅ One-click from QC to live data
- ✅ No UI hunt required
- ✅ Professional UX

---

### Option 2: Auto-Start Live Data After QC Dialog Closes

**Implementation**:
```python
# In main_simplified.py _show_qc_dialog()

self._qc_dialog = CalibrationQCDialog.show_qc_report(
    parent=self.main_window,
    calibration_data=qc_data
)

# ADD THIS:
self._qc_dialog.finished.connect(lambda: self._on_qc_dialog_closed())

def _on_qc_dialog_closed(self):
    """Auto-start live data after user reviews QC."""
    logger.info("QC dialog closed - auto-starting live data")
    from PySide6.QtWidgets import QMessageBox

    reply = QMessageBox.question(
        self.main_window,
        "Start Live Data?",
        "Calibration complete. Start live acquisition now?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.Yes
    )

    if reply == QMessageBox.StandardButton.Yes:
        self._on_start_button_clicked()
```

**Benefits**:
- ✅ Automatic workflow
- ✅ User confirmation
- ❌ Extra dialog (less clean)

---

### Option 3: Use Progress Dialog "Start" Button After Calibration

**Keep progress dialog open after calibration**:
```python
# In CalibrationService._run_calibration() (line ~258+)

# After calibration_complete.emit(), UPDATE DIALOG:
if self._calibration_dialog:
    self._calibration_dialog.update_title("✅ Calibration Complete!")
    self._calibration_dialog.update_status("Review results, then click Start to begin live acquisition.")
    self._calibration_dialog.enable_start_button()
    self._calibration_dialog.set_progress(100, 100)
    # DON'T CLOSE IT!
```

**Benefits**:
- ✅ Uses existing button logic
- ✅ Clear workflow
- ❌ Two dialogs visible (progress + QC)
- ❌ Confusing which to interact with

---

## Recommended Implementation: Option 1

### Files to Modify:

#### 1. `src/widgets/calibration_qc_dialog.py`

**Add signal** (line ~23):
```python
from PySide6.QtCore import Signal

class CalibrationQCDialog(QDialog):
    # Signal emitted when user clicks Start Live Data
    start_live_requested = Signal()
```

**Update button layout** (line ~125):
```python
# Button layout
button_layout = QHBoxLayout()
button_layout.addStretch()

close_btn = QPushButton("Close")
close_btn.clicked.connect(self.accept)
button_layout.addWidget(close_btn)

# Start Live Data button (primary action)
start_btn = QPushButton("✅ Start Live Data")
start_btn.setStyleSheet("""
    QPushButton {
        background: #34C759;
        color: white;
        border: none;
        border-radius: 6px;
        padding: 10px 20px;
        font-size: 13px;
        font-weight: 600;
        min-width: 150px;
    }
    QPushButton:hover {
        background: #30B350;
    }
    QPushButton:pressed {
        background: #28A745;
    }
""")
start_btn.clicked.connect(self._on_start_live_clicked)
button_layout.addWidget(start_btn)

layout.addLayout(button_layout)
```

**Add handler** (after _setup_ui):
```python
def _on_start_live_clicked(self):
    """Handle Start Live Data button click."""
    logger.info("🚀 User requested live data start from QC dialog")
    self.start_live_requested.emit()
    self.accept()  # Close dialog
```

#### 2. `src/main_simplified.py`

**Connect signal** (in _show_qc_dialog, line ~589):
```python
self._qc_dialog = CalibrationQCDialog.show_qc_report(
    parent=self.main_window,
    calibration_data=qc_data
)

# Connect start button to existing handler
self._qc_dialog.start_live_requested.connect(self._on_start_button_clicked)
logger.info("Connected: QC dialog start_live_requested -> _on_start_button_clicked")
```

**That's it!** The existing `_on_start_button_clicked()` handler already:
- Checks if hardware is ready
- Starts data acquisition
- Handles errors gracefully

---

## Expected User Experience After Fix

```
1. User clicks "Calibrate" → Progress dialog appears
2. User clicks "Start" → Calibration runs
3. Calibration completes → QC dialog appears
4. User reviews QC results
5. User clicks "✅ Start Live Data" →
   - QC dialog closes
   - Live acquisition begins
   - Sensorgram updates in real-time
```

**Time saved**: ~5-10 seconds of UI hunting per calibration
**Confusion eliminated**: 100%
**Professional polish**: ✨ Significantly improved

---

## Testing Checklist

### Before Fix
- [ ] Calibration completes
- [ ] QC dialog shows
- [ ] Only "Close" button visible
- [ ] User must close dialog
- [ ] User must find Start button in sidebar
- [ ] User clicks Start
- [ ] Live data begins

### After Fix
- [ ] Calibration completes
- [ ] QC dialog shows
- [ ] Both "Close" and "✅ Start Live Data" buttons visible
- [ ] User reviews QC
- [ ] User clicks "✅ Start Live Data"
- [ ] QC dialog closes automatically
- [ ] Live data begins immediately
- [ ] No need to hunt for buttons

---

## Summary

**Current Issue**: QC dialog is a dead-end - no clear path to start live data

**Root Cause**: QC dialog only has "Close" button, no integration with acquisition start

**Solution**: Add "Start Live Data" button to QC dialog that:
1. Emits `start_live_requested` signal
2. Connects to existing `_on_start_button_clicked()` handler
3. Closes dialog automatically
4. Begins live acquisition

**Impact**:
- ⏱️ Saves 5-10 seconds per calibration
- 👍 Eliminates user confusion
- 🎯 Professional, intuitive workflow
- 🔧 Minimal code changes (~20 lines)

**Priority**: HIGH - Major UX improvement
