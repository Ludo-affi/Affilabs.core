"""
Centralized UI Styles for ezControl
Modern Apple-inspired grayscale design system
Single source of truth for ALL UI styling
"""

from PySide6.QtGui import QFont


# ============================================================================
# DESIGN TOKENS - Modern Grayscale Theme (Apple-inspired)
# ============================================================================

class Colors:
    """Color palette following modern grayscale design principles"""

    # Primary grayscale colors (Apple-inspired)
    GRAY_900 = "#1D1D1F"                   # Almost black - primary dark
    GRAY_700 = "#3A3A3C"                   # Dark gray - hover states
    GRAY_600 = "#48484A"                   # Medium-dark gray
    GRAY_500 = "#86868B"                   # Mid gray - secondary text
    GRAY_300 = "rgba(0, 0, 0, 0.1)"       # Light gray - borders
    GRAY_100 = "rgba(0, 0, 0, 0.06)"      # Very light gray - backgrounds
    GRAY_50 = "#F5F5F7"                    # Off-white backgrounds

    # Surface colors
    SURFACE = "#FFFFFF"                    # Pure white backgrounds
    SURFACE_ELEVATED = "#FAFAFA"           # Slightly elevated surfaces
    BACKGROUND = "#F8F9FA"                 # Page background

    # State colors (semantic)
    SUCCESS = "#34C759"                    # Green for success
    SUCCESS_HOVER = "#2FB350"
    ERROR = "#FF3B30"                      # Red for errors
    ERROR_HOVER = "#E6342A"
    WARNING = "#FFCC00"                    # Yellow for warnings
    WARNING_HOVER = "#E6B800"

    # Channel colors (data visualization) - kept for compatibility
    CHANNEL_A = "rgb(0, 0, 0)"             # Black
    CHANNEL_B = "rgb(255, 0, 81)"          # Red/Pink
    CHANNEL_C = "rgb(0, 174, 255)"         # Blue
    CHANNEL_D = "rgb(0, 150, 80)"          # Green

    # Legacy aliases for backwards compatibility
    PRIMARY = GRAY_900
    PRIMARY_HOVER = GRAY_700
    PRIMARY_LIGHT = GRAY_100
    OUTLINE = GRAY_300
    OUTLINE_VARIANT = "rgba(0, 0, 0, 0.08)"
    ON_SURFACE = GRAY_900
    ON_SURFACE_VARIANT = GRAY_500
    SURFACE_CONTAINER = GRAY_50
    SURFACE_VARIANT = GRAY_50


class Spacing:
    """Consistent spacing system (8px base unit - Apple standard)"""
    XS = 4    # Extra small
    SM = 8    # Small
    MD = 12   # Medium
    LG = 16   # Large
    XL = 20   # Extra large
    XXL = 24  # Extra extra large


class Radius:
    """Border radius values (Apple-inspired rounded corners)"""
    NONE = 0
    SM = 4    # Small elements
    MD = 8    # Standard containers (primary radius)
    LG = 12   # Large containers
    XL = 20   # Pill-shaped buttons
    FULL = 9999  # Circular


class Shadows:
    """Subtle elevation shadows (Apple-inspired minimal shadows)"""
    ELEVATION_1 = "0 1px 2px rgba(0, 0, 0, 0.04)"
    ELEVATION_2 = "0 2px 4px rgba(0, 0, 0, 0.06)"
    ELEVATION_3 = "0 4px 8px rgba(0, 0, 0, 0.08)"


# Backwards compatibility aliases
class ChannelColors:
    """Channel colors for data visualization"""
    A = Colors.CHANNEL_A
    B = Colors.CHANNEL_B
    C = Colors.CHANNEL_C
    D = Colors.CHANNEL_D


class UIColors:
    """Legacy UI colors - use Colors.* instead"""
    BACKGROUND_LIGHT = Colors.GRAY_50
    BACKGROUND_WHITE = Colors.SURFACE
    BORDER = Colors.GRAY_300
    COMPANY_BLUE = Colors.GRAY_900  # Changed to grayscale primary
    BUTTON_HOVER = Colors.GRAY_700
    TEXT_DARK = Colors.GRAY_900


# ============================================================================
# TYPOGRAPHY - Apple SF Pro inspired
# ============================================================================

class Typography:
    """Font definitions following Apple's typography scale"""
    FAMILY = "-apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif"
    FAMILY_DISPLAY = "-apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif"

    # Font sizes (Apple-inspired scale)
    SIZE_CAPTION = 11     # Small text, captions
    SIZE_BODY_SMALL = 8   # Small body text, groupbox titles
    SIZE_BODY = 9         # Standard body text
    SIZE_SUBTITLE = 10    # Subtitles
    SIZE_TITLE = 11       # Section titles
    SIZE_HEADLINE = 13    # Large headings


def get_font(size: int = Typography.SIZE_BODY, bold: bool = False, weight: int = -1) -> 'QFont':
    """
    Create a font with specified parameters

    Args:
        size: Font size in points (default: 9)
        bold: Whether font should be bold
        weight: Explicit font weight (overrides bold if set)

    Returns:
        QFont configured with specified parameters
    """
    from PySide6.QtGui import QFont
    font = QFont(Typography.FAMILY, size)
    if weight > 0:
        font.setWeight(weight)
    elif bold:
        font.setBold(True)
    return font


# Convenience font getters
def get_groupbox_title_font():
    """Standard font for QGroupBox titles (8pt)"""
    return get_font(Typography.SIZE_BODY_SMALL)


def get_segment_checkbox_font():
    """Font for segment/channel checkboxes (9pt bold)"""
    return get_font(Typography.SIZE_BODY, bold=True)


def get_standard_font():
    """Standard body font (9pt)"""
    return get_font(Typography.SIZE_BODY)


def get_title_font():
    """Title font (11pt semi-bold)"""
    from PySide6.QtGui import QFont
    font = get_font(Typography.SIZE_TITLE)
    font.setWeight(QFont.Weight.DemiBold)
    return font


def get_small_font():
    """Small font (7pt)"""
    return get_font(Typography.SIZE_CAPTION)





# ============================================================================
# COMPONENT STYLES - Modern Grayscale Design
# ============================================================================

def get_button_style(variant: str = 'standard') -> str:
    """
    Modern grayscale button styles (Apple-inspired)

    Args:
        variant: 'standard', 'primary', 'success', 'error', 'text'

    Returns:
        Complete stylesheet string for QPushButton
    """
    variants = {
        'standard': {
            'bg': 'rgba(0, 0, 0, 0.06)',
            'hover_bg': 'rgba(0, 0, 0, 0.1)',
            'pressed_bg': 'rgba(0, 0, 0, 0.14)',
            'text': '#1D1D1F',
            'border_radius': '8px'
        },
        'primary': {
            'bg': '#1D1D1F',
            'hover_bg': '#3A3A3C',
            'pressed_bg': '#48484A',
            'text': 'white',
            'border_radius': '8px'
        },
        'success': {
            'bg': '#34C759',
            'hover_bg': '#2FB350',
            'pressed_bg': '#28A745',
            'text': 'white',
            'border_radius': '8px'
        },
        'error': {
            'bg': '#FF3B30',
            'hover_bg': '#E6342A',
            'pressed_bg': '#CC2E24',
            'text': 'white',
            'border_radius': '8px'
        },
        'text': {
            'bg': 'transparent',
            'hover_bg': 'rgba(0, 0, 0, 0.06)',
            'pressed_bg': 'rgba(0, 0, 0, 0.1)',
            'text': '#1D1D1F',
            'border_radius': '8px'
        }
    }

    style = variants.get(variant, variants['standard'])

    return f"""
    QPushButton {{
        background: {style['bg']};
        border: none;
        border-radius: {style['border_radius']};
        color: {style['text']};
        padding: 10px 16px;
        font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;
        font-size: 13px;
        font-weight: 600;
    }}

    QPushButton:hover {{
        background: {style['hover_bg']};
    }}

    QPushButton:pressed {{
        background: {style['pressed_bg']};
    }}

    QPushButton:disabled {{
        background: rgba(0, 0, 0, 0.03);
        color: #86868B;
        opacity: 0.5;
    }}
    """


def get_container_style(elevated: bool = True) -> str:
    """
    Modern container/surface style with subtle elevation

    Args:
        elevated: Whether to show elevation shadow (Note: Qt doesn't support box-shadow)

    Returns:
        Stylesheet for QFrame/QGroupBox containers
    """
    # Qt doesn't support box-shadow, use border instead for elevation effect
    border = f"border: 2px solid {Colors.PRIMARY_LIGHT};" if elevated else f"border: 1px solid {Colors.OUTLINE};"

    return f"""
    QFrame {{
        background-color: {Colors.SURFACE};
        {border}
        border-radius: {Radius.MD}px;
    }}
    """


def get_groupbox_style(background: str = Colors.SURFACE) -> str:
    """
    Material Design groupbox style

    Args:
        background: Background color

    Returns:
        Stylesheet for QGroupBox
    """
    return f"""
    QGroupBox {{
        background-color: {background};
        border: 1px solid {Colors.OUTLINE};
        border-radius: {Radius.SM}px;
        padding: {Spacing.MD}px;
        margin-top: {Spacing.MD}px;
        font-family: {Typography.FAMILY};
        font-size: {Typography.SIZE_BODY_SMALL}pt;
        color: {Colors.ON_SURFACE};
    }}

    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: {Spacing.SM}px;
        padding: 0 {Spacing.XS}px;
        background-color: {background};
    }}
    """


def get_input_style() -> str:
    """Modern input field style with rounded corners"""
    return f"""
    QLineEdit {{
        background-color: {Colors.SURFACE};
        border: 1px solid {Colors.OUTLINE};
        border-radius: {Radius.SM}px;
        padding: {Spacing.SM}px;
        font-family: {Typography.FAMILY};
        font-size: {Typography.SIZE_BODY}pt;
        color: {Colors.ON_SURFACE};
    }}

    QLineEdit:focus {{
        border: 2px solid {Colors.PRIMARY};
        background-color: {Colors.SURFACE};
    }}

    QLineEdit:disabled {{
        background-color: {Colors.SURFACE_VARIANT};
        color: {Colors.ON_SURFACE_VARIANT};
    }}
    """


def get_checkbox_style() -> str:
    """Modern checkbox style with subtle colors"""
    return f"""
    QCheckBox {{
        spacing: {Spacing.SM}px;
        font-family: {Typography.FAMILY};
        font-size: {Typography.SIZE_BODY}pt;
        color: {Colors.ON_SURFACE};
    }}

    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border-radius: {Radius.SM}px;
        border: 2px solid {Colors.OUTLINE};
        background-color: {Colors.SURFACE};
    }}

    QCheckBox::indicator:hover {{
        border-color: {Colors.PRIMARY};
        background-color: {Colors.PRIMARY_LIGHT};
    }}

    QCheckBox::indicator:checked {{
        background-color: {Colors.PRIMARY};
        border-color: {Colors.PRIMARY};
        image: url(:/img/img/check_white.png);
    }}

    QCheckBox::indicator:checked:hover {{
        background-color: {Colors.PRIMARY_HOVER};
    }}

    QCheckBox::indicator:disabled {{
        background-color: {Colors.SURFACE_VARIANT};
        border-color: {Colors.OUTLINE_VARIANT};
    }}
    """


def get_radiobutton_style() -> str:
    """Material Design radio button style"""
    return f"""
    QRadioButton {{
        spacing: {Spacing.SM}px;
        font-family: {Typography.FAMILY};
        font-size: {Typography.SIZE_BODY}pt;
        color: {Colors.ON_SURFACE};
    }}

    QRadioButton::indicator {{
        width: 18px;
        height: 18px;
        border-radius: 9px;
        border: 2px solid {Colors.OUTLINE};
        background-color: {Colors.SURFACE};
    }}

    QRadioButton::indicator:hover {{
        border-color: {Colors.PRIMARY};
        background-color: {Colors.PRIMARY_LIGHT};
    }}

    QRadioButton::indicator:checked {{
        background-color: {Colors.PRIMARY};
        border-color: {Colors.PRIMARY};
    }}

    QRadioButton::indicator:checked:hover {{
        background-color: {Colors.PRIMARY_HOVER};
    }}

    QRadioButton::indicator:disabled {{
        background-color: {Colors.SURFACE_VARIANT};
        border-color: {Colors.OUTLINE_VARIANT};
    }}
    """


def get_combobox_style() -> str:
    """Modern combobox/dropdown style with clean appearance"""
    return f"""
    QComboBox {{
        background-color: {Colors.SURFACE};
        border: 1px solid {Colors.OUTLINE};
        border-radius: {Radius.SM}px;
        padding: {Spacing.SM}px;
        font-family: {Typography.FAMILY};
        font-size: {Typography.SIZE_BODY}pt;
        color: {Colors.ON_SURFACE};
    }}

    QComboBox:hover {{
        border-color: {Colors.PRIMARY};
    }}

    QComboBox:focus {{
        border: 2px solid {Colors.PRIMARY};
    }}

    QComboBox::drop-down {{
        border: none;
        width: 20px;
    }}

    QComboBox QAbstractItemView {{
        background-color: {Colors.SURFACE};
        border: 1px solid {Colors.OUTLINE};
        selection-background-color: {Colors.PRIMARY_LIGHT};
        selection-color: {Colors.ON_SURFACE};
    }}
    """


def get_channel_checkbox_style(channel: str) -> str:
    """
    Channel-specific checkbox style with color coding

    Args:
        channel: 'A', 'B', 'C', or 'D'

    Returns:
        Stylesheet for channel checkbox
    """
    color_map = {
        'A': Colors.CHANNEL_A,
        'B': Colors.CHANNEL_B,
        'C': Colors.CHANNEL_C,
        'D': Colors.CHANNEL_D
    }

    color = color_map.get(channel.upper(), Colors.CHANNEL_A)

    return f"""
    QCheckBox {{
        color: {color};
        background-color: {Colors.SURFACE};
        border: 1px solid {Colors.OUTLINE};
        border-radius: {Radius.SM}px;
        padding: {Spacing.XS}px;
        font-family: {Typography.FAMILY};
        font-size: {Typography.SIZE_BODY}pt;
        font-weight: bold;
    }}
    """


def get_progress_bar_style() -> str:
    """Material Design progress bar style"""
    return f"""
    QProgressBar {{
        border: 1px solid {Colors.OUTLINE};
        border-radius: {Radius.SM}px;
        background-color: {Colors.SURFACE_VARIANT};
        text-align: center;
        font-family: {Typography.FAMILY};
        font-size: {Typography.SIZE_BODY_SMALL}pt;
        color: {Colors.ON_SURFACE};
    }}

    QProgressBar::chunk {{
        background-color: {Colors.PRIMARY};
        border-radius: {Radius.SM - 1}px;
    }}
    """


def get_graph_border_style() -> str:
    """Style for graph plot borders"""
    return f"""
    QFrame {{
        border: 1px solid {Colors.ON_SURFACE_VARIANT};
        border-radius: {Radius.SM}px;
        background: transparent;
    }}
    """


def get_toggle_dot_style() -> str:
    """Small dot-style radio buttons for graph toggles"""
    return f"""
    QRadioButton::indicator {{
        width: 8px;
        height: 8px;
        border-radius: 4px;
        border: 2px solid {Colors.OUTLINE};
        background: transparent;
    }}

    QRadioButton::indicator:checked {{
        background: {Colors.PRIMARY};
        border-color: {Colors.PRIMARY};
    }}
    """


# ============================================================================
# LEGACY COMPATIBILITY FUNCTIONS
# ============================================================================

def get_standard_button_style() -> str:
    """Legacy: Use get_button_style('standard') instead"""
    return get_button_style('standard')


def get_clear_button_style() -> str:
    """Legacy: Use get_button_style('text') instead"""
    return get_button_style('text')


def get_main_display_style() -> str:
    """Legacy: Main display frame style"""
    return f"""
    QFrame#main_display {{
        background-color: {Colors.SURFACE_VARIANT};
        border: none;
    }}
    """


def get_standard_container_style() -> str:
    """Legacy: Standard container style (use get_container_style() instead)"""
    return get_container_style(elevated=True)


def get_standard_radiobutton_style() -> str:
    """Legacy: Use get_radiobutton_style() instead"""
    return get_radiobutton_style()


def get_standard_checkbox_style() -> str:
    """Legacy: Use get_checkbox_style() instead"""
    return get_checkbox_style()


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def apply_channel_checkbox_style(checkbox, channel: str):
    """
    Apply standard style to a channel checkbox

    Args:
        checkbox: QCheckBox widget
        channel: 'A', 'B', 'C', or 'D'
    """
    checkbox.setFont(get_segment_checkbox_font())
    checkbox.setStyleSheet(get_channel_checkbox_style(channel))


def apply_groupbox_style(groupbox, background_color: str = "white"):
    """Apply standard style to a groupbox"""
    groupbox.setFont(get_groupbox_title_font())
    if background_color != "transparent":
        groupbox.setStyleSheet(get_groupbox_style(background_color))


def apply_standard_button_style(button):
    """Apply standard button style"""
    button.setStyleSheet(get_standard_button_style())


def apply_standard_radiobutton_style(radiobutton):
    """Apply standard radiobutton style with company blue accent"""
    radiobutton.setStyleSheet(get_standard_radiobutton_style())


def apply_standard_checkbox_style(checkbox):
    """Apply standard checkbox style with company blue accent"""
    checkbox.setStyleSheet(get_standard_checkbox_style())
