# Layout Customization Guide

## Overview
The Device Status widget and Settings panel now support flexible layout customization. You can move UI elements between widgets to create your preferred layout.

## Available Methods

### MainWindow Methods

#### `move_graph_settings_to_device_status()`
Moves the "Graph Display Settings" box from the Settings panel to the Device Status widget.
- **Returns**: `True` if successful, `False` otherwise
- **Use Case**: Consolidate all hardware-related controls in the Hardware Status section

```python
# In mainwindow.py __init__, after self.sidebar.set_widgets():
self.move_graph_settings_to_device_status()
```

#### `move_connect_button_to_device_bottom()`
Moves the Connect button to the bottom of the Device Status widget for better visibility.
- **Returns**: `True` if successful, `False` otherwise
- **Use Case**: Make the connect button more prominent

```python
self.move_connect_button_to_device_bottom()
```

#### `get_device_status_widget()`
Returns the DeviceStatusWidget instance for manual manipulation.
- **Returns**: `DeviceStatusWidget` or `None`

```python
device_status = self.get_device_status_widget()
```

#### `get_settings_panel()`
Returns the SettingsPanel instance for manual manipulation.
- **Returns**: `SettingsPanel` or `None`

```python
settings = self.get_settings_panel()
```

---

### DeviceStatusWidget Methods

#### `get_main_layout()`
Returns the main QVBoxLayout of the Hardware Status container.
- **Returns**: `QVBoxLayout`

#### `add_widget_to_layout(widget, position=-1)`
Adds a widget to the Hardware Status layout.
- **Parameters**:
  - `widget`: QWidget to add
  - `position`: Position to insert (-1 for end, before spacer)

```python
device_status = mainwindow.get_device_status_widget()
device_status.add_widget_to_layout(my_custom_widget)
```

#### `get_connect_button()`
Returns the Connect QPushButton for manipulation.
- **Returns**: `QPushButton`

#### `move_connect_button_to_layout(layout, position=-1)`
Moves the Connect button to a different layout.
- **Parameters**:
  - `layout`: Target QLayout
  - `position`: Position to insert (-1 for end)

---

### SettingsPanel Methods

#### `get_graph_display_group()`
Returns the Graph Display Settings QGroupBox.
- **Returns**: `QGroupBox`

#### `remove_graph_display_group()`
Removes and returns the Graph Display Settings box from the Settings panel.
- **Returns**: `QGroupBox` or `None`

#### `get_adjust_margins_button()`
Returns the "Adjust Graph Margins" QPushButton.
- **Returns**: `QPushButton`

---

## Usage Examples

### Example 1: Move Graph Settings to Device Status
```python
# In mainwindow.py, after UI initialization
def __init__(self, app):
    # ... existing initialization code ...

    self.sidebar.set_widgets()

    # Move graph settings to hardware status
    self.move_graph_settings_to_device_status()

    # ... rest of initialization ...
```

### Example 2: Move Connect Button
```python
# In mainwindow.py, after UI initialization
self.move_connect_button_to_device_bottom()
```

### Example 3: Both Changes
```python
# Combine both customizations
self.move_graph_settings_to_device_status()
self.move_connect_button_to_device_bottom()
```

### Example 4: Manual Custom Layout
```python
# Get widgets for manual manipulation
device_status = self.get_device_status_widget()
settings = self.get_settings_panel()

# Remove graph settings from Settings panel
graph_group = settings.remove_graph_display_group()

# Add it to device status at specific position
device_status.add_widget_to_layout(graph_group, position=3)

# Get and modify connect button
connect_btn = device_status.get_connect_button()
connect_btn.setMinimumHeight(40)  # Make it bigger
connect_btn.setText("Connect Device")  # Change text

# Move button to main layout
main_layout = device_status.get_main_layout()
device_status.move_connect_button_to_layout(main_layout, position=-1)
```

---

## Current Layout Structure

### Device Status Widget Hierarchy:
```
DeviceStatusWidget
└── main_container (QFrame)
    └── main_layout (QVBoxLayout)
        ├── main_title ("Hardware Status")
        ├── spr_frame (Device section)
        │   ├── SPR: [●] Status
        │   ├── Pump: [●] Status
        │   └── [Connect Button]
        ├── operation_frame (Operation section)
        │   ├── Static / Flow / Not Supported
        ├── system_frame (System Status section)
        │   ├── Sensor: [●] Status
        │   ├── Optics: [●] Status
        │   └── Fluidics: [●] Status
        ├── [Optional: Graph Display Settings] ← Can be added here
        └── support_link
```

### Settings Panel Hierarchy:
```
SettingsPanel
└── layout (QVBoxLayout)
    ├── graph_group (Graph Display Settings) ← Can be removed/moved
    │   ├── Description
    │   └── [Adjust Graph Margins Button]
    └── spacer
```

---

## Notes

- All methods check for widget existence and return `False` on failure
- Changes are logged to the application logger
- The connect button maintains its signal connections when moved
- Graph settings group maintains its styling when moved
- Support link always stays at the bottom of Device Status

---

## Where to Call These Methods

**Best Location**: In `mainwindow.py` in the `__init__` method, after this line:
```python
self.sidebar.set_widgets()
```

**Example**:
```python
# Line ~152 in mainwindow.py
self.sidebar.setMinimumWidth(self.sidebar_width)
self.sidebar.setMaximumWidth(self.sidebar_width)
self.sidebar.set_widgets()

# Add your customizations here:
self.move_graph_settings_to_device_status()  # ← Add this
self.move_connect_button_to_device_bottom()   # ← And/or this

# Add settings panel to Settings tab
from widgets.settings_panel import SettingsPanel
# ... rest of code ...
```
