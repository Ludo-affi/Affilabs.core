# Layout Control System - Summary

## What's Been Fixed and Added

### 1. **Non-Blocking Dialog** ✅
The margin adjustment dialog now uses `show()` instead of `exec()`, so it no longer blocks the main UI.

**Changes:**
- Dialog is non-modal (`setModal(False)`)
- Tool window that stays on top
- You can now click on sidebar tabs and interact with the main window while adjusting margins
- Cancel button properly reverts changes

### 2. **Copy Code Button** ✅
Added "📋 Copy Code" button to dialog that copies current values as Python code to clipboard.

**Usage:**
1. Adjust values in dialog
2. Click "Copy Code" button
3. Paste into your Python file
4. Button shows "✓ Copied!" confirmation

**Example output:**
```python
# Background Rectangle Margin Settings
self.bg_rect_margin_left = -2
self.bg_rect_margin_top = -9
self.bg_rect_margin_right = 16
self.bg_rect_margin_bottom = -4
self.bg_rect_radius = 8

# Update rectangle styling
if hasattr(self, 'bg_rect_widget'):
    self.bg_rect_widget.setStyleSheet(
        "background-color: rgb(255, 255, 255);"
        "border: 1px solid rgb(100, 100, 100);"
        "border-radius: {self.bg_rect_radius}px;"
    )
```

### 3. **Draggable Widget System** ✅
Created `draggable_widget.py` with classes to make any widget draggable during layout work.

**Features:**
- Click and drag to move widgets
- Shows position coordinates while dragging
- Can be enabled/disabled
- Emits position_changed signal
- Auto-generates Python code for positions

## How to Use

### Using the Dialog

1. **Open Dialog:**
   ```python
   # Click "Adjust Graph Margins" in Settings tab
   ```

2. **Adjust Values:**
   - Move sliders - changes apply in real-time
   - Click on tabs, interact with main UI
   - Dialog stays on top but doesn't block

3. **Get Code:**
   - Click "📋 Copy Code" button
   - Paste into your Python file
   - Or click OK to save, Cancel to revert

### Making Widgets Draggable

**Option 1: Using DraggableWidget base class**
```python
from widgets.draggable_widget import DraggableWidget

class MyWidget(DraggableWidget, QLabel):
    def __init__(self):
        super().__init__("Drag me!")
        self.enable_dragging()  # Enable drag mode
```

**Option 2: Convert existing widget**
```python
from widgets.draggable_widget import make_widget_draggable

my_widget = QLabel("My Widget")
make_widget_draggable(my_widget)
my_widget.enable_dragging()

# Get position updates
my_widget.position_changed.connect(lambda x, y: print(f"Moved to {x}, {y}"))
```

**Option 3: Using LayoutModeManager for multiple widgets**
```python
from widgets.draggable_widget import LayoutModeManager

# Setup
manager = LayoutModeManager()
manager.add_widget(self.my_widget, "my_widget")
manager.add_widget(self.other_widget, "other_widget")

# Enable dragging mode
manager.enable_layout_mode()

# When done, print code
manager.print_positions()
# Output:
# my_widget.move(100, 50)
# other_widget.move(200, 75)

# Or save to file
manager.save_positions_to_file("widget_positions.py")

# Disable when done
manager.disable_layout_mode()
```

## Files Modified

1. **`layout_control_dialog.py`**
   - Added "Copy Code" button
   - Added `_copy_code_to_clipboard()` method
   - Added `_generate_code()` method (can override in subclasses)
   - MarginControlDialog has custom code generator

2. **`datawindow.py`**
   - Changed from `dialog.exec()` to `dialog.show()`
   - Stores dialog reference to prevent multiple instances
   - Properly handles cancel/reject with signal connections

3. **`draggable_widget.py`** (NEW)
   - DraggableWidget base class
   - make_widget_draggable() helper function
   - LayoutModeManager for managing multiple draggable widgets

## Workflow for UI Layout Work

### Workflow 1: Using Dialog for Margins
1. Open dialog
2. Adjust sliders (see changes live)
3. Click "Copy Code"
4. Paste into your code
5. Click OK or Cancel

### Workflow 2: Using Draggable Widgets
1. Enable dragging on widget(s)
2. Click and drag to reposition
3. Position coordinates shown while dragging
4. Get code via `print_positions()` or `save_positions_to_file()`
5. Paste code into your file
6. Disable dragging

### Workflow 3: Combined Approach
1. Use dialog for fine-tuning numeric values
2. Use draggable widgets for spatial positioning
3. Copy code from both
4. Combine in your source file

## Example: Making Background Rectangle Draggable

```python
# In datawindow.py, enable layout mode
from widgets.draggable_widget import make_widget_draggable

# Make bg_rect_widget draggable
if hasattr(self, 'bg_rect_widget'):
    make_widget_draggable(self.bg_rect_widget)
    self.bg_rect_widget.enable_dragging()

    # Get position updates
    self.bg_rect_widget.position_changed.connect(
        lambda x, y: print(f"Rectangle at: x={x}, y={y}")
    )

# When you find the right position, disable dragging
self.bg_rect_widget.disable_dragging()
```

## Tips

1. **Non-blocking Dialog**: You can now interact with sidebar while dialog is open
2. **Copy Code**: Use the Copy Code button instead of manually typing values
3. **Draggable Widgets**: Enable dragging during development, disable for production
4. **Position Label**: Shows coordinates while dragging for precision
5. **Code Generation**: Both dialog and draggable widgets generate ready-to-paste code

## Status

✅ Dialog is non-blocking (uses show() not exec())
✅ Copy Code button adds to dialog
✅ Draggable widget system created
✅ LayoutModeManager for managing multiple widgets
✅ Code generation from both systems
✅ Real-time updates still work
✅ Cancel still reverts changes

The system is now "nimble" - lightweight, non-blocking, and generates code for you!
