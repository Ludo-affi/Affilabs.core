# UI Cleanup & Organization Plan

## 🎉 MAJOR UPDATE - Material Design System Implemented

**Date**: 2025-11-19
**Status**: ✅ IN PROGRESS - Design System Complete, Migration Underway

### ✅ Implementation Complete

**NEW Material Design 3-Inspired System** (`ui/styles.py` - 565 lines):
1. **Design Tokens**: Colors, Spacing (4px base), Radius, Shadows, Typography
2. **Component Generators**: 13 style functions (buttons, containers, inputs, etc.)
3. **Font System**: Complete typography scale with semantic getters
4. **Backwards Compatibility**: Legacy function names maintained
5. **Documentation**: See `STYLE_GUIDE.md` for complete reference

### 📊 Migration Status: ~30% Complete

**Fully Migrated** (100%):
- ✅ `sidebar_spectroscopy_panel.py` - All containers and graphs
- ✅ `ui_kinetic.py` - CH1/CH2 groupboxes and buttons

**Partially Migrated**:
- ⚠️ `datawindow.py` (~40%) - Clear Graph section complete
- ⚠️ `ui_sensorgram.py` (~20%) - Display groupboxes complete

**Remaining** (11+ files):
- `cycle_controls_widget.py`
- `flow_status_widget.py`
- `device_status.py`
- `prime_pump_widget.py`
- `ui_processing.py` (~50 inline styles)
- `ui_analysis.py`
- `ui_spectroscopy.py`
- And more...

---

## Current State Analysis

### ✅ What's Working Well

1. **Centralized Styles System** (`ui/styles.py`)
   - ✅ Material Design 3 inspired design tokens
   - ✅ Semantic color naming (PRIMARY, SURFACE, ON_SURFACE)
   - ✅ 4px-based spacing system
   - ✅ Complete typography scale
   - ✅ Component-based styling functions

2. **Recent Improvements**
   - Tab organization (Graphic Control, Flow, etc.)
   - Scroll areas added to sidebar tabs
   - Display groupBox moved to Graphic Control tab
   - Graph titles improved ("Full Experiment Timeline")
   - Material Design system fully implemented

### ⚠️ Migration In Progress

## 1. INLINE STYLES → CENTRALIZED STYLES

**Problem**: Many UI files still have hardcoded inline stylesheets that duplicate styling logic

**Examples Found**:
```python
# Scattered throughout codebase:
- rgb(171, 171, 171) borders hardcoded everywhere
- rgb(230, 230, 230) button backgrounds repeated
- Multiple variations of the same button style
- Channel checkbox styles defined inline in ui_processing.py, ui_analysis.py, ui_spectroscopy.py
```

**Recommendation**:
- [ ] **DECISION NEEDED**: Should we migrate ALL inline styles to centralized functions?
- [ ] Create migration script to replace inline styles with function calls
- [ ] Add new centralized functions for missing patterns

**Impact**:
- ✅ Easier to maintain consistent look
- ✅ Single place to change colors/borders
- ⚠️ Requires updating many files
- ⚠️ Generated UI files (from .ui) would need special handling

---

## 2. CONTAINER STYLING PATTERNS

**Problem**: Inconsistent container/frame styling across widgets

**Current Patterns**:
1. `pol_led_container`: white bg, 1px solid rgb(180,180,180), 8px radius
2. `spec_preview`: white bg, 1px solid rgb(180,180,180), 8px radius
3. Various inline frame styles with different borders/colors

**Recommendation**:
```python
# Add to styles.py:
def get_standard_container_style():
    """Standard white container with border and rounded corners"""
    return """
    QFrame {
        background-color: white;
        border: 1px solid rgb(180, 180, 180);
        border-radius: 8px;
    }
    """

def get_graph_border_style():
    """Dark grey 1px border for graph areas"""
    return """
    QFrame {
        border: 1px solid rgb(100, 100, 100);
        border-radius: 4px;
        background: transparent;
    }
    """
```

- [ ] **DECISION**: Standardize all containers to use these patterns?
- [ ] Update sidebar_spectroscopy_panel.py, cycle_controls_widget.py, etc.

---

## 3. COLOR CONSISTENCY

**Current Issues**:
- Some places use `rgb(180, 180, 180)` for borders
- Some places use `rgb(171, 171, 171)` for borders
- Button backgrounds: `rgb(230, 230, 230)` vs `rgb(240, 240, 240)`

**Recommendation**:
```python
class UIColors:
    # Define ONE canonical value for each use case
    BORDER_STANDARD = "rgb(180, 180, 180)"  # Main borders
    BORDER_DARK = "rgb(100, 100, 100)"      # Graph borders
    BORDER_INPUT = "rgb(171, 171, 171)"     # Input field borders
    BACKGROUND_LIGHT = "rgb(240, 240, 240)" # Light backgrounds
    BACKGROUND_WHITE = "rgb(255, 255, 255)" # Pure white
    BUTTON_STANDARD = "rgb(240, 240, 240)"  # Standard button bg
```

- [ ] **DECISION**: Which rgb values should be THE standard?
- [ ] Create search/replace script to unify all usages

---

## 4. FONT DEFINITIONS

**Current State**: Multiple inline font definitions

**Problems**:
```python
# Repeated everywhere:
font1 = QFont()
font1.setFamilies(["Segoe UI"])
font1.setPointSize(8)

font2 = QFont()
font2.setFamilies(["Segoe UI"])
font2.setPointSize(9)
font2.setBold(True)
```

**Recommendation**:
```python
# Expand styles.py with complete font set:
def get_title_font():
    """11pt Segoe UI Semi-Bold for titles"""
    font = QFont("Segoe UI", 11)
    font.setWeight(QFont.DemiBold)
    return font

def get_label_font():
    """9pt Segoe UI for labels"""
    return QFont("Segoe UI", 9)

def get_input_font():
    """9pt Segoe UI for inputs"""
    return QFont("Segoe UI", 9)
```

- [ ] **DECISION**: Create comprehensive font system?
- [ ] Map all existing font usages to standard functions

---

## 5. GROUPBOX TITLE STYLING

**Current Inconsistencies**:
- Some use blue background titles (`ui_QSPR.py`, `ui_EZSPR.py`)
- Some use standard white background with border
- Title positioning varies

**Recommendation**:
```python
def get_device_groupbox_style():
    """Blue title style for device status boxes"""
    return f"""
    QGroupBox::title {{
        margin: 0px 5px 0px 5px;
        color: white;
        background-color: {UIColors.COMPANY_BLUE};
        border-radius: 3px;
        padding: 2px 5px;
    }}
    QGroupBox {{
        border: 2px solid rgba(46, 48, 227, 150);
        border-radius: 5px;
        margin-top: 0.8em;
    }}
    """

def get_standard_groupbox_style():
    """Standard white groupbox style"""
    return f"""
    QGroupBox {{
        background-color: white;
        border: 1px solid {UIColors.BORDER_STANDARD};
        border-radius: 5px;
        padding: 10px;
    }}
    """
```

- [ ] **DECISION**: Keep two distinct styles (device vs standard)?
- [ ] Apply consistently across all groupboxes

---

## 6. BUTTON STYLE VARIATIONS

**Current Issues**:
Multiple button styles throughout:
1. Standard buttons (light grey)
2. Action buttons (green/red)
3. Small clear buttons (semi-transparent)
4. Toggle buttons (dots)

**Recommendation**:
```python
# Add to styles.py:
def get_action_button_style(color_type='default'):
    """Colored action buttons"""
    colors = {
        'default': UIColors.COMPANY_BLUE,
        'success': 'rgb(46, 227, 111)',
        'danger': 'rgb(220, 53, 69)',
        'warning': 'rgb(255, 193, 7)'
    }
    color = colors.get(color_type, colors['default'])
    return f"""
    QPushButton {{
        background-color: {color};
        color: white;
        border: 1px solid {color};
        border-radius: 4px;
        padding: 8px;
        font-weight: bold;
    }}
    QPushButton:hover {{
        opacity: 0.9;
    }}
    """

def get_toggle_dot_style():
    """Radio button styled as dots for graph toggles"""
    return """
    QRadioButton::indicator {
        width: 7px;
        height: 7px;
        border-radius: 3px;
        border: 2px solid rgb(150, 150, 150);
        background: transparent;
    }
    QRadioButton::indicator:checked {
        background: rgb(0, 102, 204);
        border-color: rgb(0, 102, 204);
    }
    """
```

- [ ] **DECISION**: Standardize all button types?
- [ ] Document when to use each type

---

## 7. WIDGET-SPECIFIC STYLING

**Problem**: Some widgets have unique one-off styles

**Examples**:
- Loop diagram styling (unique)
- Progress bar in sensorgram (unique)
- Valve indicators (unique)
- Temperature displays (unique)

**Recommendation**:
- [ ] **DECISION**: Keep unique styles in widget files OR move to styles.py?
- [ ] If moving to styles.py, create "Widget-Specific Styles" section

---

## 8. LAYOUT/SPACING STANDARDS

**Current Issues**:
- Inconsistent margins: 8px, 10px, 11px, 12px
- Inconsistent spacing: 6px, 8px, 10px
- No clear guideline

**Recommendation**:
```python
class LayoutConstants:
    """Standard spacing and margin values"""
    MARGIN_SMALL = 8
    MARGIN_STANDARD = 12
    MARGIN_LARGE = 16

    SPACING_TIGHT = 4
    SPACING_STANDARD = 8
    SPACING_RELAXED = 12

    BORDER_RADIUS_SMALL = 4
    BORDER_RADIUS_STANDARD = 8
    BORDER_RADIUS_LARGE = 12
```

- [ ] **DECISION**: Define standard spacing system?
- [ ] Apply consistently to all layouts

---

## 9. FILE ORGANIZATION

**Current Structure**:
```
ui/
  ├── styles.py ✅ (centralized styles)
  ├── ui_*.py (generated + manual UI files)
widgets/
  ├── Many widget files with inline styling
```

**Questions**:
- [ ] Should generated UI files (.py from .ui) be kept separate?
- [ ] Should we have a `ui/generated/` folder?
- [ ] Should widget-specific styles go in widget files or styles.py?

---

## 10. DOCUMENTATION NEEDS

**Current Gap**: No style guide documentation

**Recommendation**: Create `STYLE_GUIDE.md` with:
- When to use each color
- When to use each font
- Standard spacing rules
- Container hierarchy (Frame > GroupBox > Layout)
- Examples of each pattern

---

## Action Plan Priority

### 🔴 HIGH PRIORITY (Do Now)
1. **Finalize Color Constants** - Make decision on canonical RGB values
2. **Document Existing Patterns** - Create STYLE_GUIDE.md
3. **Add Missing Style Functions** - Complete styles.py with all patterns

### 🟡 MEDIUM PRIORITY (Next Sprint)
4. **Migrate Channel Checkboxes** - Replace inline styles in ui_processing, ui_analysis
5. **Standardize Container Styles** - Apply consistent frame/groupbox styling
6. **Unify Button Styles** - Replace inline button styles with functions

### 🟢 LOW PRIORITY (Future)
7. **Layout Constants** - Add spacing/margin system
8. **Widget-Specific Styles** - Decide on organization
9. **Generated UI Handling** - Create .ui → .py workflow that preserves centralized styles

---

## Questions for User

Please review and make decisions on:

1. **Color Unification**: Should we use rgb(180,180,180) OR rgb(171,171,171) as THE standard border color?

2. **Style Location**: Should ALL styles go in styles.py, or keep widget-specific styles in widget files?

3. **Migration Strategy**: Migrate everything at once, or gradually as we touch files?

4. **Generated Files**: How should we handle Qt Designer .ui files? Manual override or custom generator?

5. **Breaking Changes**: Some style changes might look slightly different. Is visual consistency worth small appearance changes?

6. **Naming Convention**: Current names like `get_standard_button_style()` - keep this pattern or change to something else?

---

## Next Steps

Once decisions are made:
1. Update styles.py with agreed-upon standards
2. Create STYLE_GUIDE.md
3. Create migration checklist
4. Begin systematic file-by-file updates
5. Add pre-commit hooks to enforce standards (optional)

---

**Status**: ⏸️ Awaiting decisions before proceeding with cleanup
**Last Updated**: 2025-11-19
