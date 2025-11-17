# Checkbox and Radio Button Styling Update

## Changes Made

### Global Stylesheet Updates (`utils/ui_styles.py`)
- **QCheckBox**: Updated to modern 8×8px indicator with 1px border
  - Checked state: Blue (#4A90E2) background with white checkmark (✓)
  - Hover: Lighter border (#707070) with slight background highlight
  - Clear visual indication when checked

- **QRadioButton**: Updated to modern 12×12px circular indicator with 1px border  
  - Checked state: Blue (#4A90E2) inner dot (6×6px)
  - Hover: Lighter border with background highlight
  - Consistent with checkbox styling

### Inline Stylesheet Removal
Removed all inline `setStyleSheet()` calls that were overriding the global theme:

#### `ui/ui_sensorgram.py`
- Removed 4 inline stylesheets (segment_A, segment_B, segment_C, segment_D)

#### `ui/ui_spectroscopy.py`
- Removed 4 inline stylesheets (segment_A, segment_B, segment_C, segment_D)

#### `ui/ui_processing.py`
- Removed 8 inline stylesheets:
  - 4 segment checkboxes (segment_A, segment_B, segment_C, segment_D)
  - 4 SOI checkboxes (SOI_A, SOI_B, SOI_C, SOI_D)

#### `ui/ui_analysis.py`
- Removed 4 inline stylesheets (segment_A, segment_B, segment_C, segment_D)

**Total: 20 inline stylesheets removed**

## Result

All checkboxes and radio buttons now use the consistent modern theme:
- **Smaller indicators** (8×8px checkboxes, 12×12px radio buttons)
- **Thinner borders** (1px instead of 2px)
- **Clearer checked state** with blue color (#4A90E2) and visible indicators
- **Consistent styling** across all pages (Sensorgram, Spectroscopy, Data Processing, Analysis, Settings)

## Implementation Details

### Settings Filter Controls
The "Enable Filter" / "Disable Filter" controls in Settings use **QRadioButton** (not QCheckBox), which now has its own updated styling to match the modern theme.

### Style Clearing Methods
Existing `_fix_checkbox_styles()` methods in:
- `widgets/datawindow.py`
- `widgets/spectroscopy.py`

These methods clear any remaining inline styles and ensure the global theme applies.

## Testing Checklist
- ✅ Sensorgram page checkboxes (segment_A/B/C/D)
- ✅ Spectroscopy page checkboxes (segment_A/B/C/D)  
- ✅ Data Processing page checkboxes (segment & SOI checkboxes)
- ✅ Analysis page checkboxes (segment_A/B/C/D)
- ✅ Settings page radio buttons (filter enable/disable, reference channel selection, unit selection)
- ✅ Settings colorblind mode checkbox

All controls should now display with modern, consistent styling.
