"""Modern Design System - Color Palette & Constants
Professional Scientific Instrument UI
"""

# ============================================================================
# PRIMARY BRAND COLORS
# ============================================================================
PRIMARY = "#1A73E8"  # Google Blue - professional, trustworthy
PRIMARY_LIGHT = "#4285F4"  # Hover states
PRIMARY_DARK = "#1557B0"  # Active/pressed states
PRIMARY_HOVER = "#1765CC"  # Hover intermediate
PRIMARY_ALPHA_10 = "rgba(26, 115, 232, 0.1)"
PRIMARY_ALPHA_20 = "rgba(26, 115, 232, 0.2)"

# ============================================================================
# SEMANTIC COLORS
# ============================================================================
SUCCESS = "#1E8E3E"  # Dark green - success states, good data
SUCCESS_LIGHT = "#34A853"
SUCCESS_DARK = "#137333"
SUCCESS_BG = "#E6F4EA"

WARNING = "#F29900"  # Amber - caution, warnings
WARNING_LIGHT = "#FBBC04"
WARNING_DARK = "#E37400"
WARNING_BG = "#FEF7E0"

ERROR = "#D93025"  # Red - errors, critical
ERROR_LIGHT = "#EA4335"
ERROR_DARK = "#A50E0E"
ERROR_BG = "#FCE8E6"

INFO = "#1A73E8"  # Blue - information
INFO_LIGHT = "#4285F4"
INFO_DARK = "#1557B0"
INFO_BG = "#E8F0FE"

# ============================================================================
# NEUTRAL PALETTE (Professional Grays)
# ============================================================================
BACKGROUND = "#E8EAED"  # App background (light grey)
SURFACE = "#FFFFFF"  # Cards, panels (pure white)
SURFACE_SECONDARY = "#F8F9FA"  # Secondary surfaces
SURFACE_ELEVATED = "#FFFFFF"  # Elevated elements
BORDER = "#DADCE0"  # Subtle borders
BORDER_STRONG = "#BDC1C6"  # Stronger borders
BORDER_LIGHT = "#E8EAED"  # Very subtle dividers
DIVIDER = "#E8EAED"  # Dividers, separators

# Text Colors
TEXT_PRIMARY = "#000000"  # Main text (pure black for maximum contrast)
TEXT_SECONDARY = "#3C4043"  # Secondary text (darker grey)
TEXT_TERTIARY = "#5F6368"  # Tertiary, hints (medium grey)
TEXT_DISABLED = "#9AA0A6"  # Disabled state (lighter grey)
TEXT_INVERSE = "#FFFFFF"  # On dark backgrounds

# ============================================================================
# GRAPH/CHANNEL COLORS (Color-blind friendly)
# ============================================================================
CHANNEL_A = "#1A73E8"  # Blue - Channel A
CHANNEL_B = "#E37400"  # Orange - Channel B (high contrast to blue)
CHANNEL_C = "#1E8E3E"  # Green - Channel C
CHANNEL_D = "#10B981"  # Bright green - Channel D (high contrast with black)

# Graph UI elements
GRID_COLOR = "#E8EAED"  # Light gray grid
AXIS_COLOR = "#6B7280"  # Axis lines and text
CURSOR_COLOR = "#EAB308"  # Yellow - cursors
SELECTION_COLOR = "rgba(59, 130, 246, 0.2)"  # Blue with alpha

# ============================================================================
# SHADOWS (Elevation/Depth)
# ============================================================================
SHADOW_SM = "0 1px 2px 0 rgba(0, 0, 0, 0.05)"
SHADOW_MD = "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)"
SHADOW_LG = "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)"
SHADOW_XL = "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)"
SHADOW_INNER = "inset 0 2px 4px 0 rgba(0, 0, 0, 0.06)"

# ============================================================================
# BORDER RADIUS
# ============================================================================
RADIUS_NONE = "0px"
RADIUS_SM = "4px"  # Small elements, inputs
RADIUS_MD = "8px"  # Buttons, cards
RADIUS_LG = "12px"  # Large panels
RADIUS_XL = "16px"  # Containers
RADIUS_FULL = "9999px"  # Pills, badges, circular

# ============================================================================
# SPACING (8px base grid)
# ============================================================================
SPACE_0 = "0px"
SPACE_1 = "4px"
SPACE_2 = "8px"
SPACE_3 = "12px"
SPACE_4 = "16px"
SPACE_5 = "20px"
SPACE_6 = "24px"
SPACE_8 = "32px"
SPACE_10 = "40px"
SPACE_12 = "48px"
SPACE_16 = "64px"

# ============================================================================
# TYPOGRAPHY
# ============================================================================
FONT_FAMILY = "'Segoe UI', 'Inter', system-ui, -apple-system, sans-serif"
FONT_MONO = "'Consolas', 'Fira Code', 'Courier New', monospace"

# Font Sizes
FONT_XS = "10px"
FONT_SM = "12px"
FONT_BASE = "14px"
FONT_LG = "16px"
FONT_XL = "20px"
FONT_2XL = "24px"
FONT_3XL = "30px"

# Font Weights
WEIGHT_REGULAR = "400"
WEIGHT_MEDIUM = "500"
WEIGHT_SEMIBOLD = "600"
WEIGHT_BOLD = "700"

# Line Heights
LINE_HEIGHT_TIGHT = "1.25"
LINE_HEIGHT_NORMAL = "1.5"
LINE_HEIGHT_RELAXED = "1.75"

# ============================================================================
# TRANSITIONS
# ============================================================================
TRANSITION_FAST = "100ms"
TRANSITION_BASE = "150ms"
TRANSITION_SLOW = "300ms"
EASING = "cubic-bezier(0.4, 0.0, 0.2, 1)"

# ============================================================================
# Z-INDEX LAYERS
# ============================================================================
Z_BASE = 0
Z_DROPDOWN = 1000
Z_STICKY = 1100
Z_MODAL_BACKDROP = 1200
Z_MODAL = 1300
Z_POPOVER = 1400
Z_TOOLTIP = 1500

# ============================================================================
# GRAPH CONSTANTS
# ============================================================================
GRAPH_BACKGROUND = SURFACE
GRAPH_FOREGROUND = TEXT_PRIMARY
GRAPH_ANTIALIASING = True
GRAPH_LINE_WIDTH = 2

# ============================================================================
# COMPONENT HEIGHTS
# ============================================================================
HEIGHT_SM = "32px"
HEIGHT_MD = "40px"
HEIGHT_LG = "48px"
HEIGHT_XL = "56px"


# ============================================================================
# EXPORT FOR QSS
# ============================================================================
def generate_qss_variables():
    """Generate QSS variable definitions for use in stylesheets."""
    return """
/* Auto-generated from design_system.py */
/* Do not edit manually - run generate_qss.py to update */
    """


if __name__ == "__main__":
    print("Design System Constants Loaded ✓")
    print(f"Primary Color: {PRIMARY}")
    print(f"Text Color: {TEXT_PRIMARY}")
    print(f"Background: {BACKGROUND}")
