# ezControl UI Style Guide
## Material Design 3 Inspired System

**Last Updated**: 2025-11-19
**Status**: ✅ Active - All new code must follow these standards

---

## 🎨 Design Philosophy

This application uses a **Material Design 3 inspired** system with:
- Clean, modern aesthetics
- Consistent spacing and sizing
- Clear visual hierarchy
- Accessible color contrasts
- Professional, scientific appearance

---

## 📐 Design Tokens

### Colors (`ui.styles.Colors`)

#### Primary Colors
```python
Colors.PRIMARY = "rgb(46, 48, 227)"      # Company blue - primary actions
Colors.PRIMARY_HOVER = "rgba(46, 48, 227, 180)"  # Hover states
Colors.PRIMARY_LIGHT = "rgba(46, 48, 227, 20)"   # Subtle highlights
```

#### Surface Colors
```python
Colors.SURFACE = "rgb(255, 255, 255)"    # Pure white - main containers
Colors.SURFACE_CONTAINER = "rgb(247, 247, 250)"  # Light grey - backgrounds
Colors.SURFACE_VARIANT = "rgb(240, 240, 243)"    # Darker variant
```

#### Border Colors
```python
Colors.OUTLINE = "rgb(180, 180, 184)"           # Standard borders
Colors.OUTLINE_VARIANT = "rgb(200, 200, 203)"   # Lighter borders
```

#### Text Colors
```python
Colors.ON_SURFACE = "rgb(28, 28, 30)"           # Primary text (dark)
Colors.ON_SURFACE_VARIANT = "rgb(70, 70, 73)"  # Secondary text (grey)
```

#### State Colors
```python
Colors.SUCCESS = "rgb(46, 227, 111)"   # Green - success messages
Colors.ERROR = "rgb(220, 53, 69)"      # Red - errors, destructive actions
Colors.WARNING = "rgb(255, 193, 7)"    # Yellow - warnings
```

#### Data Visualization (Channels)
```python
Colors.CHANNEL_A = "rgb(0, 0, 0)"      # Black
Colors.CHANNEL_B = "rgb(255, 0, 81)"   # Red/Pink
Colors.CHANNEL_C = "rgb(0, 174, 255)"  # Blue
Colors.CHANNEL_D = "rgb(0, 150, 80)"   # Green
```

---

### Spacing (`ui.styles.Spacing`)

Based on **4px base unit**:

```python
Spacing.XS = 4    # Extra small - tight spacing
Spacing.SM = 8    # Small - standard internal spacing
Spacing.MD = 12   # Medium - default container padding
Spacing.LG = 16   # Large - section spacing
Spacing.XL = 24   # Extra large - major section gaps
```

**Usage Guidelines**:
- Use `SM (8px)` for spacing between related elements
- Use `MD (12px)` for container padding
- Use `LG (16px)` for spacing between sections
- Use `XL (24px)` for major layout divisions

---

### Border Radius (`ui.styles.Radius`)

```python
Radius.NONE = 0     # Sharp corners
Radius.SM = 4       # Small elements (buttons, inputs)
Radius.MD = 8       # Standard containers
Radius.LG = 12      # Large containers
Radius.FULL = 9999  # Circular (pills, radio buttons)
```

---

### Typography (`ui.styles.Typography`)

**Font Family**: Segoe UI (system default)

**Font Sizes**:
```python
Typography.SIZE_CAPTION = 7      # Very small text (labels)
Typography.SIZE_BODY_SMALL = 8   # Small body text, groupbox titles
Typography.SIZE_BODY = 9         # Standard body text (default)
Typography.SIZE_SUBTITLE = 10    # Subtitles
Typography.SIZE_TITLE = 11       # Section titles
Typography.SIZE_HEADLINE = 13    # Large headings
```

**Font Functions**:
```python
get_font(size=9, bold=False)     # Generic font
get_groupbox_title_font()        # 8pt for groupbox titles
get_segment_checkbox_font()      # 9pt bold for channel labels
get_standard_font()              # 9pt standard body
get_title_font()                 # 11pt semi-bold for titles
get_small_font()                 # 7pt for captions
```

---

## 🧩 Component Styles

### Buttons

#### Standard Button (Default)
```python
from ui.styles import get_button_style
button.setStyleSheet(get_button_style('standard'))
```
- Light grey background
- Standard border
- Blue hover state
- **Use for**: General actions, secondary buttons

#### Primary Button
```python
button.setStyleSheet(get_button_style('primary'))
```
- Blue background
- White text
- **Use for**: Main actions, "OK", "Apply", "Save"

#### Success Button
```python
button.setStyleSheet(get_button_style('success'))
```
- Green background
- White text
- **Use for**: Positive actions, "Start", "Confirm", "Run"

#### Error/Destructive Button
```python
button.setStyleSheet(get_button_style('error'))
```
- Red background
- White text
- **Use for**: Destructive actions, "Delete", "Clear", "Reset"

#### Text Button
```python
button.setStyleSheet(get_button_style('text'))
```
- Transparent background
- Blue text
- Minimal visual weight
- **Use for**: Tertiary actions, "Cancel", "Close"

---

### Containers & Groupboxes

#### Standard Container
```python
from ui.styles import get_container_style
frame.setStyleSheet(get_container_style(elevated=True))
```
- White background
- Light grey border
- 8px border radius
- Optional shadow
- **Use for**: Main content containers, cards

#### Groupbox
```python
from ui.styles import get_groupbox_style, get_groupbox_title_font, Colors
groupbox.setStyleSheet(get_groupbox_style(Colors.SURFACE))
groupbox.setFont(get_groupbox_title_font())
```
- White or custom background
- Standard border
- Title in top-left
- 12px internal padding
- **Use for**: Logical grouping of related controls

---

### Input Fields

#### Text Input
```python
from ui.styles import get_input_style
lineedit.setStyleSheet(get_input_style())
```
- White background
- Grey border
- Blue focus border (2px)
- **Use for**: QLineEdit, text entry

#### Combobox/Dropdown
```python
from ui.styles import get_combobox_style
combobox.setStyleSheet(get_combobox_style())
```
- Matches text input styling
- Dropdown arrow indicator
- Hover and focus states
- **Use for**: QComboBox, selection lists

---

### Checkboxes & Radio Buttons

#### Standard Checkbox
```python
from ui.styles import get_checkbox_style
checkbox.setStyleSheet(get_checkbox_style())
```
- 18px rounded square indicator
- Blue when checked
- White checkmark icon
- **Use for**: Boolean options, multi-select

#### Channel Checkbox (Color-coded)
```python
from ui.styles import get_channel_checkbox_style
checkbox.setStyleSheet(get_channel_checkbox_style('A'))  # A, B, C, or D
```
- Color-coded label (black, red, blue, green)
- White background with border
- **Use for**: Channel selection (A/B/C/D data visualization)

#### Standard Radio Button
```python
from ui.styles import get_radiobutton_style
radiobutton.setStyleSheet(get_radiobutton_style())
```
- 18px circular indicator
- Blue when selected
- **Use for**: Exclusive selection, single choice

#### Toggle Dots (Graph Controls)
```python
from ui.styles import get_toggle_dot_style
radiobutton.setStyleSheet(get_toggle_dot_style())
```
- Small 8px dots
- Minimal visual weight
- **Use for**: Graph view toggles, compact switches

---

### Specialized Components

#### Progress Bar
```python
from ui.styles import get_progress_bar_style
progressbar.setStyleSheet(get_progress_bar_style())
```
- Light grey background
- Blue progress chunk
- **Use for**: QProgressBar, loading indicators

#### Graph Border
```python
from ui.styles import get_graph_border_style
frame.setStyleSheet(get_graph_border_style())
```
- Dark grey 1px border
- 4px border radius
- Transparent background
- **Use for**: Wrapping pyqtgraph widgets

---

## 📋 Usage Examples

### Creating a Standard Form Section

```python
from PySide6.QtWidgets import QGroupBox, QPushButton, QLineEdit
from ui.styles import (
    get_groupbox_style, get_groupbox_title_font,
    get_button_style, get_input_style, Colors
)

# Create groupbox
settings_group = QGroupBox("Settings")
settings_group.setFont(get_groupbox_title_font())
settings_group.setStyleSheet(get_groupbox_style(Colors.SURFACE))

# Add input field
name_input = QLineEdit()
name_input.setStyleSheet(get_input_style())

# Add buttons
save_btn = QPushButton("Save")
save_btn.setStyleSheet(get_button_style('primary'))

cancel_btn = QPushButton("Cancel")
cancel_btn.setStyleSheet(get_button_style('text'))
```

### Creating a Container with Content

```python
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel
from ui.styles import get_container_style, Colors, Typography

# Create container
container = QFrame()
container.setStyleSheet(get_container_style(elevated=True))

# Create layout with standard spacing
layout = QVBoxLayout(container)
layout.setContentsMargins(Spacing.MD, Spacing.MD, Spacing.MD, Spacing.MD)
layout.setSpacing(Spacing.SM)

# Add title
title = QLabel("Section Title")
title.setStyleSheet(f"font-size: {Typography.SIZE_TITLE}pt; font-weight: 600; color: {Colors.ON_SURFACE};")
layout.addWidget(title)
```

### Creating Channel Controls

```python
from PySide6.QtWidgets import QCheckBox
from ui.styles import apply_channel_checkbox_style

# Channel A checkbox
channel_a = QCheckBox("A")
apply_channel_checkbox_style(channel_a, 'A')  # Black label

# Channel B checkbox
channel_b = QCheckBox("B")
apply_channel_checkbox_style(channel_b, 'B')  # Red label
```

---

## ✅ Do's and ❌ Don'ts

### ✅ DO

- **Always import from `ui.styles`** - Never hardcode colors or sizes
- **Use design tokens** - `Colors.PRIMARY`, `Spacing.MD`, `Radius.SM`
- **Apply complete stylesheets** - Use provided style functions
- **Match button type to action** - Primary for main actions, error for destructive
- **Use consistent spacing** - Follow the 4px base unit system
- **Set fonts explicitly** - Use `get_*_font()` functions

### ❌ DON'T

- **Don't hardcode RGB values** - Use `Colors.*` constants
- **Don't use arbitrary spacing** - Stick to `Spacing.*` values
- **Don't mix inline styles** - Use centralized functions
- **Don't ignore hover/focus states** - They're built into the styles
- **Don't create custom borders** - Use standard `Colors.OUTLINE`
- **Don't use random font sizes** - Use `Typography.SIZE_*` values

---

## 🔄 Migration Guide

### Replacing Old Inline Styles

**Before** (inline hardcoded):
```python
button.setStyleSheet("""
    QPushButton {
        background-color: rgb(230, 230, 230);
        border: 1px solid rgb(171, 171, 171);
        border-radius: 3px;
    }
""")
```

**After** (centralized):
```python
from ui.styles import get_button_style
button.setStyleSheet(get_button_style('standard'))
```

### Replacing Old Color Constants

**Before**:
```python
border_color = "rgb(171, 171, 171)"
background = "rgb(240, 240, 240)"
```

**After**:
```python
from ui.styles import Colors
border_color = Colors.OUTLINE
background = Colors.SURFACE_VARIANT
```

---

## 🧪 Testing Checklist

When styling a new component:

- [ ] Imports from `ui.styles`
- [ ] Uses design tokens (no hardcoded values)
- [ ] Hover state works correctly
- [ ] Focus state visible (for inputs)
- [ ] Disabled state looks appropriate
- [ ] Spacing follows 4px grid
- [ ] Border radius consistent with component size
- [ ] Font size appropriate for hierarchy
- [ ] Color contrast meets accessibility standards

---

## 📚 Reference

### Quick Imports
```python
# Colors and spacing
from ui.styles import Colors, Spacing, Radius, Typography

# Fonts
from ui.styles import (
    get_font, get_groupbox_title_font, get_title_font,
    get_standard_font, get_segment_checkbox_font
)

# Component styles
from ui.styles import (
    get_button_style,           # Buttons (all variants)
    get_container_style,        # Containers/frames
    get_groupbox_style,         # Groupboxes
    get_input_style,            # Text inputs
    get_checkbox_style,         # Checkboxes
    get_radiobutton_style,      # Radio buttons
    get_combobox_style,         # Dropdowns
    get_channel_checkbox_style, # Channel checkboxes
    get_progress_bar_style,     # Progress bars
    get_graph_border_style,     # Graph borders
    get_toggle_dot_style        # Toggle dots
)

# Helper functions
from ui.styles import (
    apply_channel_checkbox_style,
    apply_groupbox_style,
    apply_standard_button_style
)
```

---

## 🆘 Getting Help

**Questions?** Check existing code examples:
- `widgets/sidebar_spectroscopy_panel.py` - Container examples
- `ui/ui_kinetic.py` - Groupbox and button examples
- `ui/ui_sensorgram.py` - Checkbox examples

**Issues?** Common problems:
- **Styles not applying**: Check import order, ensure function called
- **Colors look wrong**: Verify using `Colors.*` constants
- **Spacing inconsistent**: Use `Spacing.*` values, not custom numbers

---

**Remember**: Consistency is key! Following this guide ensures a professional, unified appearance across the entire application.
