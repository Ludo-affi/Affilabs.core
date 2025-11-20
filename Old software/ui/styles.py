"""
Centralized UI Styles for ezControl
Modern Material Design-inspired styling system
Single source of truth for ALL UI styling
"""

from PySide6.QtGui import QFont


# ============================================================================
# DESIGN TOKENS - Material Design 3 Inspired
# ============================================================================

class Colors:
    """Color palette following Material Design 3 principles"""

    # Primary colors
    PRIMARY = "rgb(46, 48, 227)"           # Company blue
    PRIMARY_HOVER = "rgba(46, 48, 227, 180)"
    PRIMARY_LIGHT = "rgba(46, 48, 227, 20)"

    # Surface colors
    SURFACE = "rgb(255, 255, 255)"         # Pure white backgrounds
    SURFACE_CONTAINER = "rgb(247, 247, 250)" # Light grey containers
    SURFACE_VARIANT = "rgb(240, 240, 243)"  # Slightly darker variant

    # Border colors
    OUTLINE = "rgb(180, 180, 184)"         # Standard borders
    OUTLINE_VARIANT = "rgb(200, 200, 203)" # Lighter borders

    # Text colors
    ON_SURFACE = "rgb(28, 28, 30)"         # Primary text
    ON_SURFACE_VARIANT = "rgb(70, 70, 73)" # Secondary text

    # State colors
    SUCCESS = "rgb(46, 227, 111)"          # Green for success
    ERROR = "rgb(220, 53, 69)"             # Red for errors
    WARNING = "rgb(255, 193, 7)"           # Yellow for warnings

    # Channel colors (data visualization)
    CHANNEL_A = "rgb(0, 0, 0)"             # Black
    CHANNEL_B = "rgb(255, 0, 81)"          # Red/Pink
    CHANNEL_C = "rgb(0, 174, 255)"         # Blue
    CHANNEL_D = "rgb(0, 150, 80)"          # Green


class Spacing:
    """Consistent spacing system (4px base unit)"""
    XS = 4    # Extra small
    SM = 8    # Small
    MD = 12   # Medium
    LG = 16   # Large
    XL = 24   # Extra large


class Radius:
    """Border radius values"""
    NONE = 0
    SM = 4    # Small elements
    MD = 8    # Standard containers
    LG = 12   # Large containers
    FULL = 9999  # Circular


class Shadows:
    """Material Design elevation shadows"""
    ELEVATION_1 = "0 1px 2px rgba(0, 0, 0, 0.05)"
    ELEVATION_2 = "0 2px 4px rgba(0, 0, 0, 0.08)"
    ELEVATION_3 = "0 4px 8px rgba(0, 0, 0, 0.12)"


# Backwards compatibility aliases
class ChannelColors:
    """Legacy channel colors (use Colors.CHANNEL_* instead)"""
    A = Colors.CHANNEL_A
    B = Colors.CHANNEL_B
    C = Colors.CHANNEL_C
    D = Colors.CHANNEL_D


class UIColors:
    """Legacy UI colors (use Colors.* instead)"""
    BACKGROUND_LIGHT = Colors.SURFACE_VARIANT
    BACKGROUND_WHITE = Colors.SURFACE
    BORDER = Colors.OUTLINE
    COMPANY_BLUE = Colors.PRIMARY
    BUTTON_HOVER = "rgb(253, 253, 253)"
    TEXT_DARK = Colors.ON_SURFACE


# ============================================================================
# TYPOGRAPHY
# ============================================================================

class Typography:
    """Font definitions following typographic scale"""
    FAMILY = "Segoe UI"

    # Font sizes
    SIZE_CAPTION = 7      # Very small text
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
# COMPONENT STYLES - Material Design Inspired
# ============================================================================

def get_button_style(variant: str = 'standard') -> str:
    """
    Material Design button styles

    Args:
        variant: 'standard', 'primary', 'success', 'error', 'text'

    Returns:
        Complete stylesheet string for QPushButton
    """
    variants = {
        'standard': {
            'bg': Colors.SURFACE_VARIANT,
            'border': Colors.OUTLINE,
            'hover_bg': Colors.SURFACE,
            'hover_border': Colors.PRIMARY,
            'text': Colors.ON_SURFACE
        },
        'primary': {
            'bg': Colors.PRIMARY,
            'border': Colors.PRIMARY,
            'hover_bg': Colors.PRIMARY_HOVER,
            'hover_border': Colors.PRIMARY_HOVER,
            'text': 'white'
        },
        'success': {
            'bg': Colors.SUCCESS,
            'border': Colors.SUCCESS,
            'hover_bg': 'rgba(46, 227, 111, 180)',
            'hover_border': 'rgba(46, 227, 111, 180)',
            'text': 'white'
        },
        'error': {
            'bg': Colors.ERROR,
            'border': Colors.ERROR,
            'hover_bg': 'rgba(220, 53, 69, 180)',
            'hover_border': 'rgba(220, 53, 69, 180)',
            'text': 'white'
        },
        'text': {
            'bg': 'transparent',
            'border': 'transparent',
            'hover_bg': Colors.PRIMARY_LIGHT,
            'hover_border': 'transparent',
            'text': Colors.PRIMARY
        }
    }

    style = variants.get(variant, variants['standard'])

    return f"""
    QPushButton {{
        background-color: {style['bg']};
        border: 1px solid {style['border']};
        border-radius: {Radius.SM}px;
        color: {style['text']};
        padding: {Spacing.SM}px {Spacing.MD}px;
        font-family: {Typography.FAMILY};
        font-size: {Typography.SIZE_BODY}pt;
    }}

    QPushButton:hover {{
        background-color: {style['hover_bg']};
        border-color: {style['hover_border']};
    }}

    QPushButton:pressed {{
        opacity: 0.8;
    }}

    QPushButton:disabled {{
        background-color: {Colors.SURFACE_VARIANT};
        border-color: {Colors.OUTLINE_VARIANT};
        color: {Colors.ON_SURFACE_VARIANT};
        opacity: 0.5;
    }}
    """


def get_container_style(elevated: bool = True) -> str:
    """
    Material Design container/surface style

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
    """Material Design input field style"""
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
    """Material Design checkbox style"""
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
    """Material Design combobox/dropdown style"""
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
