# Debug Mode: Simplified Start (No Method Upload)

**Date**: November 24, 2025
**Purpose**: Isolate software crash by stripping back to bare UI operations

## Problem Statement

After 40+ hours debugging a crash that occurs when clicking "Start" after calibration, we need to systematically isolate the issue by removing components one at a time.

## Solution: Simplified Start Mode

This implementation removes ALL hardware interaction from the Start button and focuses purely on UI operations.

---

## Changes Made

### 1. Modified Start Button Behavior
**File**: `Affilabs.core beta\main_simplified.py`
**Method**: `_on_start_button_clicked()`

**OLD Behavior**:
```python
def _on_start_button_clicked(self):
    # Check if calibrated
    if not self.data_acq_mgr or not self.data_acq_mgr.calibrated:
        # Show error
        return

    # Start live acquisition (UPLOADS METHOD TO HARDWARE)
    self.data_acq_mgr.start_acquisition()
```

**NEW Behavior**:
```python
def _on_start_button_clicked(self):
    # STEP 1: Open live data dialog (UI only, no data)
    from live_data_dialog import LiveDataDialog
    self._live_data_dialog = LiveDataDialog(parent=self.main_window)
    self._live_data_dialog.show()

    # STEP 2: Unlock UI elements (simulate post-calibration)
    self.ui.enable_recording_controls()  # Enable record/pause buttons

    # STEP 3: Set UI to "acquiring" state (cosmetic only)
    self._on_acquisition_started()  # Updates UI state

    # NO METHOD UPLOAD
    # NO HARDWARE INTERACTION
    # NO DATA ACQUISITION THREAD
```

### 2. Added Calibration Bypass Shortcut
**Keyboard Shortcut**: `Ctrl+Shift+C`
**Method**: `_debug_bypass_calibration()`

**What It Does**:
- Marks system as "calibrated" (fake data injection)
- Enables Start button
- Enables recording controls
- **NO hardware calibration runs**
- **NO hardware interaction at all**

**How to Use**:
1. Launch application
2. Press `Ctrl+Shift+C`
3. See confirmation dialog: "Calibration Bypassed (Debug)"
4. Start button is now enabled
5. Click Start to test UI without hardware

---

## Testing Strategy

### Test 1: UI Only (No Hardware)
1. Launch app
2. Press `Ctrl+Shift+C` (bypass calibration)
3. Click "Start"
4. **Expected**: Live data dialog opens, UI unlocks, NO CRASH
5. **If crash occurs**: Problem is in UI layer, not hardware/method upload

### Test 2: With Hardware Connected
1. Connect hardware
2. Press `Ctrl+Shift+C` (bypass calibration)
3. Click "Start"
4. **Expected**: Same as Test 1 - UI opens, no hardware interaction
5. **If crash occurs**: Hardware presence triggers issue (even without interaction)

### Test 3: Manual Calibration + Simplified Start
1. Connect hardware
2. Run full calibration normally
3. Click "Start"
4. **Expected**: Live dialog opens, UI unlocks, NO method upload, NO CRASH
5. **If crash occurs**: Post-calibration state has corrupted data

---

## What Was REMOVED from Start Button

| Component | Status |
|-----------|--------|
| Method upload to controller | ❌ DISABLED |
| Polarizer mode switching | ❌ DISABLED |
| Integration time setting | ❌ DISABLED |
| LED intensity setting | ❌ DISABLED |
| Data acquisition thread start | ❌ DISABLED |
| Spectrum reading | ❌ DISABLED |
| Queue processing | ❌ DISABLED |
| Hardware validation checks | ❌ DISABLED |

## What Was KEPT (UI Only)

| Component | Status |
|-----------|--------|
| Live data dialog creation | ✅ ENABLED |
| Dialog show/raise/activate | ✅ ENABLED |
| Record button unlock | ✅ ENABLED |
| Pause button unlock | ✅ ENABLED |
| Start button state update | ✅ ENABLED |
| UI state transition | ✅ ENABLED |

---

## Expected Outcomes

### If Software Still Crashes:
- **Issue is in UI layer**: Dialog creation, window management, or Qt threading in UI code
- **Next step**: Comment out dialog creation, test with just button unlocking

### If Software Does NOT Crash:
- **Issue is in hardware/method layer**: Method upload, polarizer switching, or hardware communication
- **Next step**: Add back components one at a time:
  1. Add polarizer switching (no method)
  2. Add integration time setting (no method)
  3. Add LED intensity setting (no method)
  4. Add full method upload

---

## Reverting Changes

To restore normal operation:

1. **Comment out new Start button code** in `main_simplified.py`:
   ```python
   # Restore original _on_start_button_clicked() implementation
   ```

2. **Remove or comment out keyboard shortcut**:
   ```python
   # bypass_calibration_shortcut = QShortcut(QKeySequence("Ctrl+Shift+C"), self.main_window)
   # bypass_calibration_shortcut.activated.connect(self._debug_bypass_calibration)
   ```

3. **Remove `_debug_bypass_calibration()` method** (optional cleanup)

---

## Debug Logging

Look for these log messages:

```
🚀 User requested start - SIMPLIFIED MODE (UI only, no method upload)
📊 Opening live data dialog (UI only)...
✅ Live data dialog opened
🔓 Unlocking UI elements (simulating post-calibration)...
✅ UI elements unlocked
🎭 Setting UI to 'acquiring' state (cosmetic only)...
✅ UI state updated
✅ SIMPLIFIED START COMPLETE - UI ready, no hardware interaction
```

If crash occurs AFTER these messages, the issue is in the UI layer.
If crash occurs BEFORE these messages, the issue is in button click handling.

---

## Files Modified

1. `Affilabs.core beta\main_simplified.py`
   - Modified: `_on_start_button_clicked()`
   - Added: `_debug_bypass_calibration()`
   - Modified: Keyboard shortcut registration

---

## Next Steps

After testing:

1. **Document which test case crashes** (if any)
2. **Identify the exact log line before crash**
3. **Add back components incrementally** based on results
4. **Binary search to find the problematic line of code**

This systematic approach will finally isolate the root cause after 40+ hours of investigation.
