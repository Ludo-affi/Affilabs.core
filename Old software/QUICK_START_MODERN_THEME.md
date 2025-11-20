# 🎯 Quick Start Guide - Using the Modern Theme

## Immediate Usage (Already Working!)

The modern theme is now integrated and will apply automatically when you run the application!

### To Run with Modern Theme:
```bash
cd "Old software"
python main/main.py
```

The application will automatically:
1. ✅ Load modern QSS theme
2. ✅ Apply professional color palette
3. ✅ Style all PyQtGraph plots
4. ✅ Set modern fonts

---

## For Developers: Using the Theme System

### 1. Import the Theme
```python
from styles import (
    apply_modern_theme,
    get_color,
    set_primary_button_style,
    set_secondary_button_style,
    set_success_button_style,
    set_danger_button_style,
    set_card_style,
)
```

### 2. Style Buttons
```python
# Old way (DELETE THIS):
button.setStyleSheet(
    "QPushButton{\n"
    "	background: rgb(207, 207, 207);\n"
    "}\n"
)

# New way (USE THIS):
from styles import set_primary_button_style
set_primary_button_style(button)

# Or for different button types:
set_secondary_button_style(cancel_button)
set_success_button_style(save_button)
set_danger_button_style(delete_button)
```

### 3. Use Design System Colors
```python
# Old way (DELETE THIS):
color = "rgb(46, 48, 227)"

# New way (USE THIS):
from styles import PRIMARY, CHANNEL_A, SUCCESS
color = PRIMARY  # or CHANNEL_A, SUCCESS, etc.
```

### 4. Style Containers
```python
# Apply card styling to a frame:
from styles import set_card_style
set_card_style(my_frame)

# Apply toolbar styling:
from styles import set_toolbar_style
set_toolbar_style(my_toolbar)
```

### 5. Graph Styling
```python
# Old way:
pen = mkPen(color=settings.ACTIVE_GRAPH_COLORS[ch], width=2)

# New way:
from styles import create_channel_pens
channel_pens = create_channel_pens()
pen = channel_pens['a']  # or 'b', 'c', 'd'
```

---

## 🔍 Finding Code to Modernize

### Search for These Patterns:

1. **Inline StyleSheets**:
```python
# Find:
widget.setStyleSheet(

# Replace with:
# (Use theme classes instead)
```

2. **Hardcoded Colors**:
```python
# Find:
rgb(
#HEXCOLOR
QColor(

# Replace with:
# (Use design system constants)
```

3. **Hardcoded Fonts**:
```python
# Find:
setFont(
font-size:
font-family:

# Replace with:
# (Theme handles this automatically)
```

---

## 📋 Migration Checklist

### Phase 1: Main Window (1 hour)
- [ ] Remove inline styles from mainwindow.py
- [ ] Apply theme classes to buttons
- [ ] Use design system colors
- [ ] Test power button, record button, pause button

### Phase 2: Sidebar (1 hour)
- [ ] Remove inline styles from sidebar.py
- [ ] Apply card styling to sections
- [ ] Modernize device controls
- [ ] Update kinetic controls

### Phase 3: Data Window (1.5 hours)
- [ ] Remove inline styles from datawindow.py
- [ ] Apply card styling to panels
- [ ] Update table styling
- [ ] Modernize segment controls

### Phase 4: Graphs (1 hour)
- [ ] Update SensorgramGraph colors
- [ ] Update SegmentGraph colors
- [ ] Apply modern cursor styling
- [ ] Test with live data

### Phase 5: Other Widgets (1 hour)
- [ ] spectroscopy.py
- [ ] analysis.py
- [ ] settings_menu.py
- [ ] advanced.py

### Phase 6: Testing (1 hour)
- [ ] Test all pages
- [ ] Test all buttons
- [ ] Test all inputs
- [ ] Test graphs with real data
- [ ] Screenshots for comparison

---

## 🎨 Design System Quick Reference

### Colors
```python
# Brand
PRIMARY = "#2E30E3"          # Main blue
PRIMARY_LIGHT = "#6668FF"    # Hover
PRIMARY_DARK = "#1A1CCF"     # Active

# Semantic
SUCCESS = "#2EE36F"          # Green
WARNING = "#FFB84D"          # Orange
ERROR = "#FF4D4D"            # Red
INFO = "#4D9FFF"             # Light blue

# Neutrals
BACKGROUND = "#F5F7FA"       # App background
SURFACE = "#FFFFFF"          # Cards/panels
TEXT_PRIMARY = "#1F2937"     # Main text
TEXT_SECONDARY = "#6B7280"   # Secondary text

# Channels
CHANNEL_A = "#3B82F6"        # Blue
CHANNEL_B = "#10B981"        # Green
CHANNEL_C = "#F59E0B"        # Amber
CHANNEL_D = "#EF4444"        # Red
```

### Spacing (8px grid)
```python
SPACE_1 = "4px"
SPACE_2 = "8px"
SPACE_3 = "12px"
SPACE_4 = "16px"
SPACE_6 = "24px"
SPACE_8 = "32px"
```

### Border Radius
```python
RADIUS_SM = "4px"   # Inputs
RADIUS_MD = "8px"   # Buttons, cards
RADIUS_LG = "12px"  # Panels
```

---

## 🐛 Troubleshooting

### Theme Not Loading?
```python
# Check console for:
"✨ Applying modern UI theme..."
"✅ Modern theme applied successfully"

# If you see warnings, theme system may not be in path
# Verify: Old software/styles/ directory exists
```

### Styles Not Applying?
```python
# After changing a widget's property, refresh:
widget.setProperty("class", "primary")
widget.style().unpolish(widget)
widget.style().polish(widget)
widget.update()
```

### Colors Look Wrong?
```python
# Make sure you're using design system constants:
from styles import PRIMARY, SUCCESS, CHANNEL_A

# NOT hardcoded values:
color = "#2E30E3"  # BAD
color = PRIMARY    # GOOD
```

---

## 📸 Before/After Comparison

### Take Screenshots!
1. **Before**: Run old version, capture screenshots
2. **After**: Run with modern theme, capture screenshots
3. Compare side-by-side for presentation

### Key Areas to Capture:
- Main window overview
- Sidebar controls
- Data processing view
- Graph views (sensorgram, segment)
- Settings dialogs
- Tables and forms

---

## 🎯 Expected Results

### Visual Changes:
- ✅ Cleaner, more modern appearance
- ✅ Better contrast and readability
- ✅ Consistent styling throughout
- ✅ Professional color palette
- ✅ Smooth, polished feel

### Technical Benefits:
- ✅ Easier to maintain (centralized styles)
- ✅ Faster development (reusable components)
- ✅ Better code organization
- ✅ Future-proof architecture

### Business Impact:
- ✅ Higher perceived value
- ✅ Increased customer confidence
- ✅ Better competitive position
- ✅ Premium pricing justified

---

## 💡 Tips for Best Results

1. **Do It Incrementally**: Migrate one widget at a time, test thoroughly
2. **Use Version Control**: Commit after each successful migration
3. **Test on Real Hardware**: Make sure it works with actual device
4. **Get Feedback**: Show to users/stakeholders early
5. **Document Changes**: Note any issues or improvements needed

---

## 🚀 Ready to Ship?

Once migration is complete:
1. ✅ All inline styles removed
2. ✅ All colors from design system
3. ✅ All widgets using theme classes
4. ✅ Thoroughly tested
5. ✅ Screenshots/demo ready

**You'll have a professional, modern UI that looks like it costs $50,000!**

---

## 📞 Need Help?

The theme system is designed to be simple and intuitive. If you run into issues:

1. Check this guide
2. Look at design_system.py for available colors/constants
3. Look at modern_theme.qss for available classes
4. Check theme_manager.py for helper functions

**Remember: The goal is zero inline styles and maximum use of the design system!**

Let's make this the best-looking SPR instrument software on the market! 🚀
