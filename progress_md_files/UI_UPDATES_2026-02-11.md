# UI Updates & Fixes - February 11, 2026

This document describes all UI updates and critical bug fixes applied to AffiLabs.core. Use this to quickly rebuild these features if lost.

---

## Table of Contents
1. [Critical Timing Bug Fix](#1-critical-timing-bug-fix)
2. [Excel Loading Fixes](#2-excel-loading-fixes)
3. [Cycle Timing Editor](#3-cycle-timing-editor)
4. [Operation Status Bar](#4-operation-status-bar)

---

## 1. Critical Timing Bug Fix

### Issue
Cycle `end_time_sensorgram` was **never set** before export, causing timing mismatches between live data and Edits table.

### Root Cause
```python
# main.py line 2859-2865 - BEFORE FIX
end_sensorgram_time = None
if hasattr(self.main_window, 'full_timeline_graph'):
    timeline = self.main_window.full_timeline_graph
    if hasattr(timeline, 'stop_cursor'):
        end_sensorgram_time = timeline.stop_cursor.value()

# ❌ Variable calculated but NEVER assigned to cycle object!
# Then cycle.to_export_dict() exports end_time_sensorgram as None
```

### Fix Applied

**File:** `main.py`

**Location 1:** After line 2865 (normal cycle completion)
```python
# CRITICAL: Set end time on cycle object before export
if end_sensorgram_time is not None:
    self._current_cycle.end_time_sensorgram = end_sensorgram_time
    logger.debug(f"✓ Cycle end time set: {end_sensorgram_time:.2f}s")
```

**Location 2:** After line 3093 (early cycle completion via Next Cycle button)
```python
# CRITICAL: Set end time on cycle object before export
if end_sensorgram_time is not None:
    self._current_cycle.end_time_sensorgram = end_sensorgram_time
    logger.debug(f"✓ Cycle end time set (early completion): {end_sensorgram_time:.2f}s")
```

### Result
✅ Live data timing now matches Edits table timing
✅ `start_time_sensorgram` and `end_time_sensorgram` both correctly set
✅ Duration calculations accurate
✅ Excel exports have complete timing info

---

## 2. Excel Loading Fixes

### Issues
1. `CycleTypeStyle` not imported → NameError
2. NaN values in Excel crashed formatting
3. String-encoded dicts/lists not parsed

### Fixes Applied

**File:** `affilabs/tabs/edits_tab.py`

#### Fix 1: Add Missing Import (Line 24)
```python
from affilabs.widgets.ui_constants import CycleTypeStyle
```

#### Fix 2: NaN Handling in Table Population (Lines 1333-1391)

**Time Column:**
```python
# Handle NaN values
if pd.notna(duration_min) and pd.notna(start_time) and isinstance(duration_min, (int, float)) and isinstance(start_time, (int, float)):
    time_str = f"{duration_min:.1f}m @ {start_time:.0f}s"
else:
    time_str = f"{duration_min}m @ {start_time}s" if duration_min != 0 or start_time != 0 else "—"
```

**Concentration Column:**
```python
conc_val = cycle.get('concentration_value', '')
conc_str = str(conc_val) if pd.notna(conc_val) and conc_val != '' else ''
```

**ΔSPR Column:**
```python
for ch_key, ch_label in [('delta_ch1', 'A'), ('delta_ch2', 'B'), ('delta_ch3', 'C'), ('delta_ch4', 'D')]:
    val = cycle.get(ch_key, '')
    if pd.notna(val) and isinstance(val, (int, float)):
        delta_parts.append(f"{ch_label}:{val:.0f}")
```

**Flags Column:**
```python
raw_flags = cycle.get('flags', '')
# Handle string representation of list
if isinstance(raw_flags, str) and raw_flags.startswith('['):
    import ast
    try:
        raw_flags = ast.literal_eval(raw_flags)
    except:
        pass
if isinstance(raw_flags, list) and raw_flags:
    flags_display = ', '.join(raw_flags)
else:
    flags_display = str(raw_flags) if raw_flags and pd.notna(raw_flags) else ''
```

#### Fix 3: Parse String-Encoded Dicts
```python
delta_by_ch = cycle.get('delta_spr_by_channel', {})
if isinstance(delta_by_ch, str):
    # If it's a string representation of dict, try to parse it
    import ast
    try:
        delta_by_ch = ast.literal_eval(delta_by_ch)
    except:
        delta_by_ch = {}
```

### Result
✅ Excel files load without errors
✅ NaN values display as blank instead of crashing
✅ String-encoded data parsed correctly
✅ Table displays complete cycle information

---

## 3. Cycle Timing Editor

### Feature
Right-click context menu option to manually edit cycle start/end times in Edits tab.

### Implementation

**File:** `affilabs/tabs/edits_tab.py`

#### Step 1: Add Menu Option (Line 2580)
```python
if len(selected_rows) == 1:
    # Single cycle selected - offer to edit timing
    edit_action = menu.addAction("✏️ Edit Cycle Timing")
    edit_action.triggered.connect(lambda: self._edit_cycle_timing(selected_rows[0]))

    menu.addSeparator()
```

#### Step 2: Add Dialog Method (After line 2682)
```python
def _edit_cycle_timing(self, row_index):
    """Open dialog to manually edit cycle start/end times.

    Args:
        row_index: Row index in cycle table
    """
    from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QDoubleSpinBox, QPushButton, QFormLayout
    from affilabs.utils.logger import logger

    # Get current cycle data
    if not hasattr(self.main_window, '_loaded_cycles_data') or row_index >= len(self.main_window._loaded_cycles_data):
        logger.warning(f"Cannot edit cycle timing - row {row_index} not found in loaded data")
        return

    cycle_data = self.main_window._loaded_cycles_data[row_index]

    # Get current values
    current_start = cycle_data.get('start_time_sensorgram', 0)
    current_end = cycle_data.get('end_time_sensorgram', 0)
    current_duration = cycle_data.get('duration_minutes', 0)

    # Handle NaN values
    if pd.isna(current_start):
        current_start = 0
    if pd.isna(current_end):
        current_end = current_start + (current_duration * 60 if not pd.isna(current_duration) else 0)
    if pd.isna(current_duration):
        current_duration = (current_end - current_start) / 60 if current_end > current_start else 0

    # Create dialog
    dialog = QDialog(self.main_window)
    dialog.setWindowTitle(f"Edit Timing - Cycle {row_index + 1}")
    dialog.setMinimumWidth(400)

    layout = QVBoxLayout(dialog)
    layout.setSpacing(16)

    # Info label
    cycle_type = cycle_data.get('type', 'Unknown')
    info_label = QLabel(f"<b>{cycle_type} (Cycle {row_index + 1})</b>")
    info_label.setStyleSheet("font-size: 14px; color: #1D1D1F; padding: 8px;")
    layout.addWidget(info_label)

    # Form layout for timing inputs
    form_layout = QFormLayout()
    form_layout.setSpacing(12)

    # Start time input (seconds)
    start_spin = QDoubleSpinBox()
    start_spin.setRange(0, 999999)
    start_spin.setValue(current_start)
    start_spin.setSuffix(" s")
    start_spin.setDecimals(2)
    start_spin.setMinimumWidth(150)
    start_spin.setStyleSheet("""
        QDoubleSpinBox {
            padding: 6px;
            font-size: 13px;
            border: 1px solid #D1D1D6;
            border-radius: 6px;
        }
        QDoubleSpinBox:focus {
            border: 2px solid #007AFF;
        }
    """)
    form_layout.addRow("Start Time:", start_spin)

    # End time input (seconds)
    end_spin = QDoubleSpinBox()
    end_spin.setRange(0, 999999)
    end_spin.setValue(current_end)
    end_spin.setSuffix(" s")
    end_spin.setDecimals(2)
    end_spin.setMinimumWidth(150)
    end_spin.setStyleSheet(start_spin.styleSheet())
    form_layout.addRow("End Time:", end_spin)

    # Duration (calculated, read-only display)
    duration_label = QLabel(f"{current_duration:.2f} min")
    duration_label.setStyleSheet("font-size: 13px; color: #86868B; padding: 6px;")
    form_layout.addRow("Duration:", duration_label)

    # Auto-update duration when times change
    def update_duration():
        start = start_spin.value()
        end = end_spin.value()
        duration_min = (end - start) / 60
        duration_label.setText(f"{duration_min:.2f} min")
        # Validate times
        if end <= start:
            duration_label.setStyleSheet("font-size: 13px; color: #FF3B30; padding: 6px; font-weight: 600;")
        else:
            duration_label.setStyleSheet("font-size: 13px; color: #86868B; padding: 6px;")

    start_spin.valueChanged.connect(update_duration)
    end_spin.valueChanged.connect(update_duration)

    layout.addLayout(form_layout)

    # Button row
    button_layout = QHBoxLayout()
    button_layout.addStretch()

    cancel_btn = QPushButton("Cancel")
    cancel_btn.setFixedHeight(36)
    cancel_btn.setStyleSheet("""
        QPushButton {
            background: #F2F2F7;
            color: #1D1D1F;
            border: none;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 600;
            padding: 0 20px;
        }
        QPushButton:hover {
            background: #E5E5EA;
        }
    """)
    cancel_btn.clicked.connect(dialog.reject)
    button_layout.addWidget(cancel_btn)

    save_btn = QPushButton("✓ Save")
    save_btn.setFixedHeight(36)
    save_btn.setStyleSheet("""
        QPushButton {
            background: #007AFF;
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 600;
            padding: 0 20px;
        }
        QPushButton:hover {
            background: #0051D5;
        }
    """)

    def save_changes():
        new_start = start_spin.value()
        new_end = end_spin.value()

        # Validate
        if new_end <= new_start:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                dialog,
                "Invalid Timing",
                "End time must be after start time!"
            )
            return

        # Update cycle data
        cycle_data['start_time_sensorgram'] = new_start
        cycle_data['end_time_sensorgram'] = new_end
        cycle_data['duration_minutes'] = (new_end - new_start) / 60

        # Update table display
        time_str = f"{cycle_data['duration_minutes']:.1f}m @ {new_start:.0f}s"
        self.cycle_data_table.item(row_index, 1).setText(time_str)

        logger.info(f"✏️ Updated cycle {row_index + 1} timing: {new_start:.2f}s → {new_end:.2f}s ({cycle_data['duration_minutes']:.2f} min)")

        # Show confirmation
        if hasattr(self.main_window, 'sidebar') and hasattr(self.main_window.sidebar, 'intel_message_label'):
            self.main_window.sidebar.intel_message_label.setText(
                f"✏️ Updated Cycle {row_index + 1} timing"
            )
            self.main_window.sidebar.intel_message_label.setStyleSheet(
                "font-size: 12px; color: #34C759; background: transparent; font-weight: 600;"
            )

        dialog.accept()

    save_btn.clicked.connect(save_changes)
    button_layout.addWidget(save_btn)

    layout.addLayout(button_layout)

    # Show dialog
    dialog.exec()
```

### Usage
1. Right-click any cycle row in Edits table
2. Select "✏️ Edit Cycle Timing"
3. Adjust start/end times
4. Duration auto-calculates
5. Click "✓ Save" to apply changes

### Result
✅ Manual timing correction for imported data
✅ Fixes NaN end times from old data
✅ Real-time duration validation
✅ Clean Apple-style UI

---

## 4. Operation Status Bar

### Feature
Bottom status bar showing current operation (e.g., "Running: Concentration (01:52 remaining)", "Idle").

### Implementation

**File:** `affilabs/affilabs_core_ui.py`

#### Step 1: Add Status Bar Widget (After line 1422)
```python
# Create vertical layout for main content + status bar
content_with_status_layout = QVBoxLayout()
content_with_status_layout.setContentsMargins(0, 0, 0, 0)
content_with_status_layout.setSpacing(0)
content_with_status_layout.addWidget(self.splitter)

# Add operation status bar at bottom (matches navigation bar style)
self.operation_status_bar = QFrame()
self.operation_status_bar.setFixedHeight(36)
self.operation_status_bar.setStyleSheet(f"""
    QFrame {{
        background: {Colors.BACKGROUND_WHITE};
        border-top: 1px solid {Colors.OVERLAY_LIGHT_10};
    }}
""")

status_layout = QHBoxLayout(self.operation_status_bar)
status_layout.setContentsMargins(20, 0, 20, 0)
status_layout.setSpacing(12)

# Operation status label (uses system font and colors)
self.operation_status_label = QLabel("Idle")
self.operation_status_label.setStyleSheet(
    label_style(12, color=Colors.SECONDARY_TEXT, weight=int(Fonts.WEIGHT_MEDIUM))
)
status_layout.addWidget(self.operation_status_label)

status_layout.addStretch()

content_with_status_layout.addWidget(self.operation_status_bar)

# Wrap in container widget
content_with_status_widget = QWidget()
content_with_status_widget.setLayout(content_with_status_layout)

main_layout.addWidget(content_with_status_widget)
```

#### Step 2: Add Update Method (Before line 6128)
```python
def update_status_operation(self, message: str) -> None:
    """Update the bottom operation status bar.

    Args:
        message: Status message to display (e.g., "Running: Concentration (01:52)", "Idle")
    """
    if hasattr(self, 'operation_status_label'):
        self.operation_status_label.setText(message)
        # Color based on state using design system colors
        if "Running" in message or "Acquiring" in message:
            color = Colors.SUCCESS  # Green for active operations
            weight = int(Fonts.WEIGHT_SEMIBOLD)
        elif "Idle" in message:
            color = Colors.SECONDARY_TEXT  # Gray for idle
            weight = int(Fonts.WEIGHT_MEDIUM)
        elif "Error" in message or "Failed" in message:
            color = Colors.ERROR  # Red for errors
            weight = int(Fonts.WEIGHT_SEMIBOLD)
        else:
            color = Colors.INFO  # Blue for other states
            weight = int(Fonts.WEIGHT_MEDIUM)

        self.operation_status_label.setStyleSheet(
            label_style(12, color=color, weight=weight)
        )
```

### Design System Integration
- **Background:** `Colors.BACKGROUND_WHITE` (#FFFFFF) - matches navigation bar
- **Border:** `Colors.OVERLAY_LIGHT_10` - subtle separation
- **Height:** 36px - consistent spacing
- **Margins:** 20px - matches navigation bar
- **Font:** System font stack (`Fonts.SYSTEM`)
- **Colors:**
  - 🟢 `Colors.SUCCESS` (#34C759) - Running/Acquiring
  - ⚪ `Colors.SECONDARY_TEXT` (#86868B) - Idle
  - 🔴 `Colors.ERROR` (#FF3B30) - Errors
  - 🔵 `Colors.INFO` (#007AFF) - Other states

### Automatic Updates
The status bar updates automatically via existing calls in `main.py`:
- Line 2365: When cycle starts
- Line 2910: When cycle completes (sets to "Idle")

### Result
✅ Professional status bar at bottom of UI
✅ Matches navigation bar design perfectly
✅ Auto-updates during cycle execution
✅ Color-coded status indicators
✅ Consistent with Apple design language

---

## Quick Rebuild Checklist

If you need to rebuild these features:

### 1. Cycle Timing Fix
- [ ] Add 4 lines after line 2865 in `main.py`
- [ ] Add 4 lines after line 3093 in `main.py`

### 2. Excel Loading
- [ ] Add import at line 24 in `edits_tab.py`
- [ ] Add NaN checks in `_populate_cycles_table()` method

### 3. Timing Editor
- [ ] Add menu option in `_on_table_context_menu()`
- [ ] Add `_edit_cycle_timing()` method

### 4. Status Bar
- [ ] Modify `_setup_ui()` to add status bar widget
- [ ] Add `update_status_operation()` method

---

## Files Modified

1. `main.py` - Cycle timing bug fix
2. `affilabs/tabs/edits_tab.py` - Excel loading + timing editor
3. `affilabs/affilabs_core_ui.py` - Operation status bar

---

## Testing

### Test Cycle Timing Fix
1. Run a cycle
2. Check Edits table - start/end times should be populated
3. Export to Excel - verify timing columns are complete

### Test Excel Loading
1. Load Excel file with old data
2. Should load without NameError
3. NaN values display as blank

### Test Timing Editor
1. Right-click cycle in Edits table
2. Select "Edit Cycle Timing"
3. Modify times and save
4. Verify table updates

### Test Status Bar
1. Start application
2. Look for white bar at bottom showing "Idle"
3. Start a cycle - should show "Running: ..." in green
4. Complete cycle - should return to "Idle" in gray

---

*Generated: February 11, 2026*
*Session: UI Updates & Critical Bug Fixes*
