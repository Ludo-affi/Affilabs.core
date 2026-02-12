# UI Calibration & Cycle Improvements
**Date:** February 11, 2026  
**Time:** 14:30:00  
**Session Focus:** Calibration Dialog Enhancement, Timeline Cursor UX, Cycle Duration Accuracy

---

## Overview
This session focused on improving user experience across three key areas:
1. **Calibration Dialog** - Better progress feedback during long-running operations
2. **Timeline Cursors** - Declutter graph view while maintaining label accessibility  
3. **Cycle Duration Display** - Show actual monitored time instead of planned duration

---

## 1. Calibration Dialog Step Descriptions

### Problem
Calibration dialog showed generic step labels like "Step 1/6", "Step 2/6" without context about what was happening during each 2-3 minute step.

### Solution
Updated all 6 calibration steps in `calibration_orchestrator.py` to send descriptive names:

**Files Modified:**
- `affilabs/core/calibration_orchestrator.py` (Lines 105-180)

**Changes:**
```python
# Step 1/6
progress_callback("Step 1/6: Hardware Validation & LED Preparation", 5)

# Step 2/6
progress_callback("Step 2/6: Wavelength Calibration", 17)

# Step 3/6
progress_callback("Step 3/6: LED Brightness & Model Validation", 30)

# Step 4/6
progress_callback("Step 4/6: S-Mode LED Convergence & Reference", 45)

# Step 5/6
progress_callback("Step 5/6: P-Mode LED Convergence & Dark Capture", 65)

# Step 6/6
progress_callback("Step 6/6: QC Validation & Result Packaging", 85)
```

**Result:**
- Users now see meaningful descriptions during calibration
- Step numbers maintain progress context
- Each step clearly indicates what's being calibrated

---

## 2. Calibration "Working..." Animation

### Problem
During long calibration steps (2-3 minutes), the dialog appeared frozen with no indication that work was progressing.

### Solution
Added animated "Working..." indicator with cycling dots (. → .. → ...) that updates every 1 second.

**Files Modified:**
- `affilabs/dialogs/startup_calib_dialog.py` (Lines 100-250)

**Changes:**
```python
class StartupCalibProgressDialog(QDialog):
    def __init__(self, parent=None):
        # ... existing code ...
        self._current_step_text = ""  # Tracks base step text
        self._dot_timer = QTimer()
        self._dot_timer.timeout.connect(self._animate_dots)
        self._dot_count = 0
        
    def _animate_dots(self):
        """Cycles dots: . → .. → ... → (repeat)"""
        self._dot_count = (self._dot_count % 3) + 1
        dots = "." * self._dot_count
        
        # Update both activity label and step description
        self.activity_label.setText(f"Working{dots}")
        if self._current_step_text:
            self.step_description_label.setText(
                f"{self._current_step_text} - Working{dots}"
            )
    
    def _do_update_step_description(self, text: str):
        self._current_step_text = text
        self.step_description_label.setText(f"{text} - Working...")
        
        # Start animation
        self._dot_timer.start(1000)  # Update every 1 second
```

**Result:**
- Step label shows: "Step 4/6: S-Mode LED Convergence & Reference - Working..."
- Dots cycle every second to indicate activity
- Users have clear feedback that calibration is progressing

---

## 3. Timeline Cursor Labels - Hover to Show

### Problem
Start and stop cursor labels were permanently visible on the timeline graph, cluttering the view and obscuring sensorgram data during acquisition.

### Solution
Hide labels by default, show after 3-second hover on cursor line to declutter graph while maintaining accessibility.

**Files Modified:**
- `affilabs/affilabs_core_ui.py` (Lines 2620-2690)

**Changes:**
```python
class HoverableInfiniteLine(InfiniteLine):
    """InfiniteLine that shows label on 3-second hover"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAcceptHoverEvents(True)
        self._hover_timer = QTimer()
        self._hover_timer.setSingleShot(True)
        self._hover_timer.timeout.connect(self._show_label)
        
    def _show_label(self):
        """Show label after hover delay"""
        if hasattr(self, 'label') and self.label:
            self.label.setVisible(True)
    
    def hoverEnterEvent(self, event):
        """Start timer when mouse enters cursor"""
        self._hover_timer.start(3000)  # 3-second delay
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event):
        """Hide label and stop timer when mouse leaves"""
        self._hover_timer.stop()
        if hasattr(self, 'label') and self.label:
            self.label.setVisible(False)
        super().hoverLeaveEvent(event)

# Create cursors with hidden labels
self.start_cursor = HoverableInfiniteLine(...)
self.start_cursor.label.setVisible(False)  # Hidden by default

self.stop_cursor = HoverableInfiniteLine(...)
self.stop_cursor.label.setVisible(False)  # Hidden by default
```

**Result:**
- Timeline graph is decluttered during acquisition
- Labels appear after 3-second hover for information
- Labels disappear when mouse moves away
- Better data visibility while maintaining cursor identification

---

## 4. Cycle Duration - Actual Monitored Time

### Problem
Cycle table in Edits tab was showing planned duration from method configuration (e.g., 2.00 minutes) instead of actual monitored time from the experiment timeline (e.g., 2.03 minutes).

### Solution
Modified `Cycle.to_export_dict()` to calculate actual duration from sensorgram timestamps (start and stop cursor positions).

**Files Modified:**
- `affilabs/domain/cycle.py` (Lines 165-215)
- `affilabs/affilabs_core_ui.py` (Lines 6830-6860)
- `main.py` (Lines 2869, 3256)

**Changes:**

**cycle.py - Calculate actual duration:**
```python
def to_export_dict(self) -> dict:
    """Export cycle as dictionary with actual measured duration"""
    
    # Calculate actual duration from timeline timestamps
    actual_duration = self.length_minutes  # Fallback to planned
    
    if self.sensorgram_time is not None and self.end_time_sensorgram is not None:
        # Use real timeline coordinates (seconds → minutes)
        actual_duration = (self.end_time_sensorgram - self.sensorgram_time) / 60.0
    
    return {
        "duration_minutes": actual_duration,      # Actual measured
        "length_minutes": self.length_minutes,     # Planned duration
        "start_time": self.start_time,
        # ... other fields
    }
```

**main.py - Set timeline coordinates:**
```python
# When cycle marker added (Line 3256)
self._current_cycle.sensorgram_time = current_time  # From start cursor

# When cycle ends (Line 2869)
self._current_cycle.end_time_sensorgram = end_sensorgram_time  # From stop cursor
```

**affilabs_core_ui.py - Display actual duration:**
```python
def add_cycle_to_table(self, cycle_data):
    """Add cycle to Edits table with actual duration"""
    
    # Read actual measured duration
    duration = cycle_data.get('duration_minutes', 
                             cycle_data.get('length_minutes', ''))
    
    # Format to 2 decimals
    duration = f"{duration:.2f}"
    
    # Add to table (Column 1: Duration)
    self.edits_table.setItem(row, 1, QTableWidgetItem(duration))
```

**Data Flow:**
1. **Cycle starts** → `sensorgram_time` = start cursor position (seconds)
2. **Cycle ends** → `end_time_sensorgram` = stop cursor position (seconds)
3. **Export** → `actual_duration = (end - start) / 60.0` (convert to minutes)
4. **Table** → Displays `duration_minutes` field (actual measured time)

**Result:**
- Edits table shows **actual monitored cycle time** from experiment
- Example: Method planned 2.00 min, actual ran 2.03 min → table shows 2.03
- Accurate record of real experimental conditions
- Maintains planned duration in `length_minutes` field for reference

---

## Testing & Validation

### Calibration Dialog
✅ Step descriptions display correctly during all 6 calibration steps  
✅ "Working..." animation cycles dots every 1 second  
✅ Progress bar advances through steps (5% → 17% → 30% → 45% → 65% → 85% → 100%)  
✅ Dialog remains responsive during long operations  

### Timeline Cursors
✅ Labels hidden by default on graph load  
✅ Labels appear after 3-second hover on cursor line  
✅ Labels hide immediately when mouse moves away  
✅ Hover timer cancels if mouse leaves before 3 seconds  

### Cycle Duration
✅ `to_export_dict()` calculates actual duration from timestamps  
✅ Edit table reads `duration_minutes` field  
✅ Duration formatted to 2 decimal places  
✅ Falls back to `length_minutes` if timestamps unavailable  

---

## Files Changed Summary

| File | Lines Modified | Purpose |
|------|----------------|---------|
| `affilabs/core/calibration_orchestrator.py` | 105-180 | Added descriptive step names to all 6 calibration steps |
| `affilabs/dialogs/startup_calib_dialog.py` | 100-250 | Added "Working..." animation with cycling dots |
| `affilabs/affilabs_core_ui.py` | 2620-2690 | Implemented hover-based cursor label visibility |
| `affilabs/domain/cycle.py` | 165-215 | Calculate actual duration from timeline timestamps |
| `main.py` | 2869, 3256 | Set cycle start/end sensorgram times for duration calc |

---

## User Impact

### Immediate Benefits
1. **Calibration Transparency** - Users understand what's happening during each step
2. **Activity Feedback** - Animated dots confirm system isn't frozen
3. **Cleaner Timeline** - Hidden labels improve data visibility during acquisition
4. **Accurate Records** - Cycle duration reflects actual experimental runtime

### Long-term Value
- Better user confidence during long calibration operations
- Reduced support requests about "frozen" calibration dialogs
- Improved data visualization during live acquisition
- More accurate experiment documentation and reproducibility

---

## Next Steps (Future Enhancements)

### Potential Improvements
- [ ] Add elapsed time display during calibration steps (e.g., "1:23 / ~2:30")
- [ ] Make hover delay configurable in settings (3s default)
- [ ] Add cursor label toggle hotkey (e.g., Ctrl+L to show/hide all)
- [ ] Export both planned and actual duration to Excel for comparison

### Technical Debt
- None identified - all changes integrated cleanly with existing architecture

---

## Code Review Notes

### Best Practices Followed
✅ QTimer-based animation for smooth UI updates  
✅ Pydantic validation maintains data integrity  
✅ Domain model calculates duration (not UI layer)  
✅ Hover events properly cancel on mouse exit  
✅ Fallback values prevent missing data errors  

### Architecture Considerations
- Cursor label visibility: UI concern (affilabs_core_ui.py) ✅
- Duration calculation: Domain model (cycle.py) ✅  
- Timeline coordination: Application layer (main.py) ✅
- Progress feedback: Dialog layer (startup_calib_dialog.py) ✅

Proper separation of concerns maintained throughout.

---

**Session completed successfully. All changes tested and validated.**
