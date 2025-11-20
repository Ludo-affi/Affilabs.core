# Nimble Layout Control Dialog - Quick Reference

## Overview
A lightweight, reusable dialog pattern for live UI layout adjustments. Non-modal, real-time updates, stays on top.

## Key Features
- **Non-Modal**: Interact with main UI while dialog is open
- **Real-Time**: Changes apply instantly as you adjust controls
- **Revertible**: Cancel button restores original state
- **Tool Window**: Stays on top, compact design
- **Reusable**: Easy to extend for new control types

## Quick Start - Using Existing Dialogs

### Margin Adjustment Dialog
```python
from widgets.margin_adjust_dialog import MarginAdjustDialog

# Current margin values
current_margins = {
    'left': 0,
    'top': 0,
    'right': 0,
    'bottom': 0,
    'radius': 6
}

# Store original for cancel
self._original_margins = current_margins.copy()

# Create dialog
dialog = MarginAdjustDialog(current_margins, parent=self)
dialog.margins_changed.connect(self.apply_margin_changes)

# Show and handle result
result = dialog.exec()
if result == MarginAdjustDialog.DialogCode.Rejected:
    self.apply_margin_changes(self._original_margins)  # Revert on cancel
```

### Position Control Dialog
```python
from widgets.layout_control_dialog import PositionControlDialog

current_position = {
    'x': 100,
    'y': 50,
    'width': 300,
    'height': 200,
    'visible': True
}

self._original_position = current_position.copy()

dialog = PositionControlDialog(current_position, parent=self)
dialog.values_changed.connect(self.apply_position_changes)

result = dialog.exec()
if result == PositionControlDialog.DialogCode.Rejected:
    self.apply_position_changes(self._original_position)
```

## Creating Custom Dialogs

### Method 1: Extend LayoutControlDialog

```python
from widgets.layout_control_dialog import LayoutControlDialog
from PySide6.QtWidgets import QGroupBox, QGridLayout, QLabel, QSpinBox, QCheckBox

class MyCustomDialog(LayoutControlDialog):
    """Custom dialog for your specific controls."""

    def __init__(self, current_values: dict, parent=None):
        super().__init__(
            title="My Custom Controls",
            description="Adjust settings in real-time. Changes apply as you adjust.",
            current_values=current_values,
            parent=parent
        )

    def _setup_controls(self):
        """Add your specific controls here."""
        # Create a group box
        group = QGroupBox("My Settings")
        layout = QGridLayout(group)
        layout.setSpacing(10)

        # Add controls
        layout.addWidget(QLabel("Setting 1:"), 0, 0)
        self.setting1_spin = QSpinBox()
        self.setting1_spin.setRange(0, 100)
        self.setting1_spin.valueChanged.connect(self._on_value_changed)
        layout.addWidget(self.setting1_spin, 0, 1)

        layout.addWidget(QLabel("Setting 2:"), 1, 0)
        self.setting2_check = QCheckBox("Enable")
        self.setting2_check.stateChanged.connect(self._on_value_changed)
        layout.addWidget(self.setting2_check, 1, 1)

        # Add to dialog
        self.controls_layout.addWidget(group)

    def _load_values(self, values: dict):
        """Load values into your controls."""
        self.setting1_spin.setValue(values.get('setting1', 50))
        self.setting2_check.setChecked(values.get('setting2', True))

    def get_values(self) -> dict:
        """Return current values from your controls."""
        return {
            'setting1': self.setting1_spin.value(),
            'setting2': self.setting2_check.isChecked()
        }
```

### Method 2: Quick Single-Purpose Dialog

```python
from widgets.layout_control_dialog import LayoutControlDialog
from PySide6.QtWidgets import QSlider, QLabel
from PySide6.QtCore import Qt

class OpacityDialog(LayoutControlDialog):
    """Simple opacity adjustment dialog."""

    def __init__(self, current_opacity: float, parent=None):
        super().__init__(
            title="Adjust Opacity",
            description="Slide to adjust transparency (0 = invisible, 100 = solid)",
            current_values={'opacity': int(current_opacity * 100)},
            parent=parent
        )

    def _setup_controls(self):
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setTickInterval(10)
        self.opacity_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.opacity_slider.valueChanged.connect(self._on_value_changed)

        self.opacity_label = QLabel("50%")
        self.opacity_slider.valueChanged.connect(
            lambda v: self.opacity_label.setText(f"{v}%")
        )

        self.controls_layout.addWidget(self.opacity_slider)
        self.controls_layout.addWidget(self.opacity_label)

    def _load_values(self, values: dict):
        self.opacity_slider.setValue(values.get('opacity', 100))

    def get_values(self) -> dict:
        return {'opacity': self.opacity_slider.value() / 100.0}
```

## Usage Pattern

### Standard Pattern (with cancel revert)
```python
def open_my_control_dialog(self):
    # 1. Get current values
    current = self.get_current_values()

    # 2. Store for cancel
    self._original = current.copy()

    # 3. Create dialog
    dialog = MyCustomDialog(current, parent=self)
    dialog.values_changed.connect(self.apply_values)

    # 4. Show and handle cancel
    result = dialog.exec()
    if result == dialog.DialogCode.Rejected:
        self.apply_values(self._original)
```

## Control Types You Can Use

- **QSpinBox**: Integer values with +/- buttons
- **QDoubleSpinBox**: Decimal values
- **QSlider**: Drag slider for values
- **QCheckBox**: Boolean on/off
- **QRadioButton**: Single choice from options
- **QComboBox**: Dropdown selection
- **QLineEdit**: Text input
- **Custom widgets**: Anything that emits signals!

## Tips for Nimble Dialogs

1. **Keep it focused**: One dialog = one task (margins, position, colors, etc.)
2. **Real-time feedback**: Connect valueChanged to `_on_value_changed()`
3. **Good tooltips**: Help users understand what each control does
4. **Logical grouping**: Use QGroupBox to organize related controls
5. **Sensible ranges**: Set min/max that make sense for your use case
6. **Compact design**: Dialog width 350-450px is ideal for tool windows

## Example: Creating a Color Picker Dialog

```python
from widgets.layout_control_dialog import LayoutControlDialog
from PySide6.QtWidgets import QGroupBox, QVBoxLayout, QSlider, QLabel, QHBoxLayout
from PySide6.QtCore import Qt

class ColorPickerDialog(LayoutControlDialog):
    """RGB color picker with live preview."""

    def __init__(self, current_color: dict, parent=None):
        super().__init__(
            title="Pick Color",
            description="Adjust RGB values. Preview updates in real-time.",
            current_values=current_color,
            parent=parent
        )

    def _setup_controls(self):
        group = QGroupBox("RGB Values")
        layout = QVBoxLayout(group)

        # Red slider
        r_layout = QHBoxLayout()
        r_layout.addWidget(QLabel("R:"))
        self.r_slider = QSlider(Qt.Orientation.Horizontal)
        self.r_slider.setRange(0, 255)
        self.r_slider.valueChanged.connect(self._on_value_changed)
        r_layout.addWidget(self.r_slider)
        self.r_label = QLabel("0")
        r_layout.addWidget(self.r_label)
        self.r_slider.valueChanged.connect(lambda v: self.r_label.setText(str(v)))
        layout.addLayout(r_layout)

        # Green slider
        g_layout = QHBoxLayout()
        g_layout.addWidget(QLabel("G:"))
        self.g_slider = QSlider(Qt.Orientation.Horizontal)
        self.g_slider.setRange(0, 255)
        self.g_slider.valueChanged.connect(self._on_value_changed)
        g_layout.addWidget(self.g_slider)
        self.g_label = QLabel("0")
        g_layout.addWidget(self.g_label)
        self.g_slider.valueChanged.connect(lambda v: self.g_label.setText(str(v)))
        layout.addLayout(g_layout)

        # Blue slider
        b_layout = QHBoxLayout()
        b_layout.addWidget(QLabel("B:"))
        self.b_slider = QSlider(Qt.Orientation.Horizontal)
        self.b_slider.setRange(0, 255)
        self.b_slider.valueChanged.connect(self._on_value_changed)
        b_layout.addWidget(self.b_slider)
        self.b_label = QLabel("0")
        b_layout.addWidget(self.b_label)
        self.b_slider.valueChanged.connect(lambda v: self.b_label.setText(str(v)))
        layout.addLayout(b_layout)

        self.controls_layout.addWidget(group)

        # Preview box
        self.preview = QLabel("Preview")
        self.preview.setMinimumHeight(50)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setStyleSheet("border: 1px solid gray;")
        self.controls_layout.addWidget(self.preview)

    def _load_values(self, values: dict):
        self.r_slider.setValue(values.get('r', 0))
        self.g_slider.setValue(values.get('g', 0))
        self.b_slider.setValue(values.get('b', 0))
        self._update_preview()

    def _on_value_changed(self):
        self._update_preview()
        super()._on_value_changed()

    def _update_preview(self):
        r = self.r_slider.value()
        g = self.g_slider.value()
        b = self.b_slider.value()
        self.preview.setStyleSheet(
            f"background-color: rgb({r}, {g}, {b}); "
            f"border: 1px solid gray; "
            f"color: {'white' if (r+g+b) < 384 else 'black'};"
        )

    def get_values(self) -> dict:
        return {
            'r': self.r_slider.value(),
            'g': self.g_slider.value(),
            'b': self.b_slider.value()
        }
```

Usage:
```python
current_color = {'r': 46, 'g': 48, 'b': 227}  # Blue
self._original_color = current_color.copy()

dialog = ColorPickerDialog(current_color, parent=self)
dialog.values_changed.connect(self.apply_color)

result = dialog.exec()
if result == dialog.DialogCode.Rejected:
    self.apply_color(self._original_color)
```

---

## Architecture

```
LayoutControlDialog (base class)
├── Non-modal setup
├── Tool window flags
├── Real-time signal emission
├── Cancel revert handling
└── Common UI structure

MarginControlDialog (example)
├── Inherits base functionality
├── Margin-specific controls
└── margins_changed signal alias

YourCustomDialog (your dialogs)
├── Inherits base functionality
├── Your specific controls
└── values_changed signal
```

The nimble dialog pattern makes it easy to create consistent, responsive control dialogs throughout your application!
