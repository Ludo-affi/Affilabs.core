"""UI Stylesheet Constants and Style Builders
Centralized styling for consistent UI appearance across the application.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QGraphicsDropShadowEffect


# ============================================================================
# COLOR PALETTE
# ============================================================================


class Colors:
    """Color constants following Apple's design system."""

    # Neutral colors
    PRIMARY_TEXT = "#1D1D1F"
    SECONDARY_TEXT = "#86868B"
    BACKGROUND_WHITE = "#FFFFFF"
    BACKGROUND_LIGHT = "#F5F5F7"
    TRANSPARENT = "transparent"

    # Surface colors (compatibility with ui/styles.py)
    SURFACE = "#FFFFFF"  # Pure white backgrounds
    ON_SURFACE = "#1D1D1F"  # Text on surface
    ON_SURFACE_VARIANT = "#86868B"  # Secondary text on surface

    # Semantic colors
    SUCCESS = "#34C759"
    WARNING = "#FF9500"
    ERROR = "#FF3B30"
    INFO = "#007AFF"

    # Alpha overlays (for backgrounds)
    OVERLAY_LIGHT_3 = "rgba(0, 0, 0, 0.03)"
    OVERLAY_LIGHT_4 = "rgba(0, 0, 0, 0.04)"
    OVERLAY_LIGHT_6 = "rgba(0, 0, 0, 0.06)"
    OVERLAY_LIGHT_8 = "rgba(0, 0, 0, 0.08)"
    OVERLAY_LIGHT_10 = "rgba(0, 0, 0, 0.1)"
    OVERLAY_LIGHT_20 = "rgba(0, 0, 0, 0.2)"
    OVERLAY_LIGHT_30 = "rgba(0, 0, 0, 0.3)"

    # Button colors
    BUTTON_PRIMARY = "#1D1D1F"
    BUTTON_PRIMARY_HOVER = "#3A3A3C"
    BUTTON_PRIMARY_PRESSED = "#48484A"
    BUTTON_DISABLED = "#86868B"


# ============================================================================
# TYPOGRAPHY
# ============================================================================


class Fonts:
    """Font family constants."""

    SYSTEM = "-apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif"
    DISPLAY = "-apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif"
    MONOSPACE = "-apple-system, 'SF Mono', 'Menlo', monospace"

    # Font weights
    WEIGHT_NORMAL = "400"
    WEIGHT_MEDIUM = "500"
    WEIGHT_SEMIBOLD = "600"
    WEIGHT_BOLD = "700"


# ============================================================================
# COMMON DIMENSIONS
# ============================================================================


class Dimensions:
    """Common sizing constants."""

    BORDER_RADIUS_SM = "6px"
    BORDER_RADIUS_MD = "8px"
    BORDER_RADIUS_LG = "12px"

    BUTTON_HEIGHT_SM = "32px"
    BUTTON_HEIGHT_MD = "36px"
    BUTTON_HEIGHT_LG = "44px"

    # Layout margins (for setContentsMargins)
    MARGIN_SM = 12
    MARGIN_MD = 16
    MARGIN_LG = 20

    # Layout spacing (for setSpacing)
    SPACING_SM = 8
    SPACING_MD = 12
    SPACING_LG = 16

    # Widget heights (for setFixedHeight)
    HEIGHT_BUTTON_SM = 24
    HEIGHT_BUTTON_MD = 28
    HEIGHT_BUTTON_STD = 32
    HEIGHT_BUTTON_LG = 36
    HEIGHT_BUTTON_XL = 40
    HEIGHT_INPUT = 36


# ============================================================================
# SPACING & RADIUS (Compatibility with ui/styles.py)
# ============================================================================


class Spacing:
    """Consistent spacing system (8px base unit - Apple standard)."""

    XS = 4  # Extra small
    SM = 8  # Small
    MD = 12  # Medium
    LG = 16  # Large
    XL = 20  # Extra large
    XXL = 24  # Extra extra large


class Radius:
    """Border radius values (Apple-inspired rounded corners)."""

    NONE = 0
    SM = 4  # Small elements
    MD = 8  # Standard containers (primary radius)
    LG = 12  # Large containers
    XL = 20  # Pill-shaped buttons
    FULL = 9999  # Circular


# ============================================================================
# COLOR UTILITIES
# ============================================================================


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color string to RGB tuple.

    Args:
        hex_color: Hex color string (e.g., "#FF5733" or "FF5733")

    Returns:
        RGB tuple (e.g., (255, 87, 51))

    """
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


# ============================================================================
# STYLESHEET BUILDERS
# ============================================================================


def label_style(
    font_size: int,
    color: str = Colors.PRIMARY_TEXT,
    weight: int = 400,
    font_family: str = Fonts.SYSTEM,
) -> str:
    """Generate consistent label stylesheet.

    Args:
        font_size: Font size in pixels
        color: Text color (default: primary text)
        weight: Font weight (default: 400)
        font_family: Font family (default: system font)

    Returns:
        Complete stylesheet string

    """
    return (
        f"font-size: {font_size}px;"
        f"color: {color};"
        f"background: transparent;"
        f"font-weight: {weight};"
        f"font-family: {font_family};"
    )


def section_header_style(font_size: int = 11, uppercase: bool = True) -> str:
    """Generate section header stylesheet (like "HARDWARE CONNECTED").

    Args:
        font_size: Font size in pixels (default: 11)
        uppercase: Whether text should be uppercase (default: True)

    Returns:
        Complete stylesheet string

    """
    style = (
        f"font-size: {font_size}px;"
        f"font-weight: 700;"
        f"color: {Colors.SECONDARY_TEXT};"
        f"background: transparent;"
        f"letter-spacing: 0.5px;"
        f"margin-left: 4px;"
        f"font-family: {Fonts.SYSTEM};"
    )
    if uppercase:
        style += "text-transform: uppercase;"
    return style


def title_style(font_size: int = 20) -> str:
    """Generate title stylesheet for main section titles.

    Args:
        font_size: Font size in pixels (default: 20)

    Returns:
        Complete stylesheet string

    """
    return (
        f"font-size: {font_size}px;"
        f"font-weight: 600;"
        f"color: {Colors.PRIMARY_TEXT};"
        f"background: transparent;"
        f"line-height: 1.2;"
        f"letter-spacing: -0.3px;"
        f"font-family: {Fonts.DISPLAY};"
    )


def card_style(
    background: str = Colors.OVERLAY_LIGHT_3,
    radius: str = Dimensions.BORDER_RADIUS_MD,
) -> str:
    """Generate card/frame stylesheet.

    Args:
        background: Background color (default: light overlay)
        radius: Border radius (default: 8px)

    Returns:
        Complete stylesheet string

    """
    return f"QFrame {{  background: {background};  border-radius: {radius};}}"


def primary_button_style(height: str = Dimensions.BUTTON_HEIGHT_MD) -> str:
    """Generate primary button stylesheet (dark background).

    Args:
        height: Button height (default: 36px)

    Returns:
        Complete stylesheet string

    """
    return (
        f"QPushButton {{"
        f"  background: {Colors.BUTTON_PRIMARY};"
        f"  color: white;"
        f"  border: none;"
        f"  border-radius: {Dimensions.BORDER_RADIUS_MD};"
        f"  padding: 0px 16px;"
        f"  font-size: 13px;"
        f"  font-weight: 600;"
        f"  text-align: center;"
        f"  font-family: {Fonts.SYSTEM};"
        f"}}"
        f"QPushButton:hover {{"
        f"  background: {Colors.BUTTON_PRIMARY_HOVER};"
        f"}}"
        f"QPushButton:pressed {{"
        f"  background: {Colors.BUTTON_PRIMARY_PRESSED};"
        f"}}"
    )


def checkbox_style() -> str:
    """Generate checkbox stylesheet with modern appearance.

    Returns:
        Complete stylesheet string

    """
    return (
        f"QCheckBox {{"
        f"  font-size: 13px;"
        f"  color: {Colors.PRIMARY_TEXT};"
        f"  background: transparent;"
        f"  spacing: 6px;"
        f"  font-weight: 500;"
        f"  font-family: {Fonts.SYSTEM};"
        f"}}"
        f"QCheckBox::indicator {{"
        f"  width: 18px;"
        f"  height: 18px;"
        f"  border: 1.5px solid {Colors.OVERLAY_LIGHT_20};"
        f"  border-radius: 4px;"
        f"  background: white;"
        f"}}"
        f"QCheckBox::indicator:hover {{"
        f"  border-color: {Colors.OVERLAY_LIGHT_30};"
        f"}}"
        f"QCheckBox::indicator:checked {{"
        f"  background: {Colors.BUTTON_PRIMARY};"
        f"  border-color: {Colors.BUTTON_PRIMARY};"
        f"  image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iOSIgdmlld0JveD0iMCAwIDEyIDkiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTEgNC41TDQuNSA4TDExIDEiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+PC9zdmc+);"
        f"}}"
        f"QCheckBox::indicator:disabled {{"
        f"  background: {Colors.OVERLAY_LIGHT_6};"
        f"  border-color: {Colors.OVERLAY_LIGHT_10};"
        f"}}"
    )


def radio_button_style() -> str:
    """Generate radio button stylesheet with modern appearance.

    Returns:
        Complete stylesheet string

    """
    return (
        f"QRadioButton {{"
        f"  font-size: 12px;"
        f"  color: {Colors.PRIMARY_TEXT};"
        f"  background: transparent;"
        f"  spacing: 4px;"
        f"  font-family: {Fonts.SYSTEM};"
        f"}}"
        f"QRadioButton::indicator {{"
        f"  width: 14px;"
        f"  height: 14px;"
        f"  border: 1px solid {Colors.OVERLAY_LIGHT_20};"
        f"  border-radius: 7px;"
        f"  background: white;"
        f"}}"
        f"QRadioButton::indicator:checked {{"
        f"  background: {Colors.BUTTON_PRIMARY};"
        f"  border: 3px solid white;"
        f"  outline: 1px solid {Colors.BUTTON_PRIMARY};"
        f"}}"
    )


def slider_style() -> str:
    """Generate slider stylesheet with modern appearance.

    Returns:
        Complete stylesheet string

    """
    return (
        f"QSlider::groove:horizontal {{"
        f"  background: {Colors.OVERLAY_LIGHT_10};"
        f"  height: 4px;"
        f"  border-radius: 2px;"
        f"}}"
        f"QSlider::handle:horizontal {{"
        f"  background: {Colors.BUTTON_PRIMARY};"
        f"  border: none;"
        f"  width: 16px;"
        f"  height: 16px;"
        f"  border-radius: 8px;"
        f"  margin: -6px 0;"
        f"}}"
        f"QSlider::handle:horizontal:hover {{"
        f"  background: {Colors.BUTTON_PRIMARY_HOVER};"
        f"}}"
        f"QSlider::handle:horizontal:disabled {{"
        f"  background: {Colors.BUTTON_DISABLED};"
        f"}}"
    )

def create_card_shadow() -> QGraphicsDropShadowEffect:
    """Create standard drop shadow effect for cards and panels.

    Returns:
        Configured QGraphicsDropShadowEffect with standard settings
        (blur=8, color=QColor(0,0,0,20), offset=(0,2))
    """
    from PySide6.QtWidgets import QGraphicsDropShadowEffect
    from PySide6.QtGui import QColor

    shadow = QGraphicsDropShadowEffect()
    shadow.setBlurRadius(8)
    shadow.setColor(QColor(0, 0, 0, 20))
    shadow.setOffset(0, 2)
    return shadow

def scrollbar_style() -> str:
    """Generate scrollbar stylesheet for scroll areas.

    Returns:
        Complete stylesheet string

    """
    return (
        f"QScrollArea {{"
        f"  background: {Colors.BACKGROUND_WHITE};"
        f"  border: none;"
        f"}}"
        f"QScrollBar:vertical {{"
        f"  background: {Colors.BACKGROUND_LIGHT};"
        f"  width: 10px;"
        f"  border-radius: 5px;"
        f"}}"
        f"QScrollBar::handle:vertical {{"
        f"  background: {Colors.OVERLAY_LIGHT_20};"
        f"  border-radius: 5px;"
        f"  min-height: 20px;"
        f"}}"
        f"QScrollBar::handle:vertical:hover {{"
        f"  background: {Colors.OVERLAY_LIGHT_30};"
        f"}}"
        f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{"
        f"  height: 0px;"
        f"}}"
    )


def separator_style() -> str:
    """Generate horizontal separator/divider stylesheet.

    Returns:
        Complete stylesheet string

    """
    return f"background: {Colors.OVERLAY_LIGHT_6};max-height: 1px;margin: 4px 0px;"


def status_indicator_style(color: str = Colors.SECONDARY_TEXT) -> str:
    """Generate status indicator (colored dot) stylesheet.

    Args:
        color: Indicator color (default: gray/not ready)

    Returns:
        Complete stylesheet string

    """
    return (
        f"font-size: 14px;"
        f"color: {color};"
        f"background: transparent;"
        f"font-family: {Fonts.SYSTEM};"
    )


def collapsible_header_style() -> str:
    """Generate collapsible section header button stylesheet.

    Returns:
        Complete stylesheet string

    """
    return (
        "QPushButton {"
        f"  background: {Colors.OVERLAY_LIGHT_4};"
        "  border: none;"
        f"  border-radius: {Dimensions.BORDER_RADIUS_SM};"
        "  padding: 8px 12px;"
        "  margin-bottom: 2px;"
        "  text-align: left;"
        "  font-size: 14px;"
        "  font-weight: 600;"
        f"  color: {Colors.PRIMARY_TEXT};"
        f"  font-family: {Fonts.SYSTEM};"
        "}"
        "QPushButton:hover {"
        f"  background: {Colors.OVERLAY_LIGHT_8};"
        "}"
        "QPushButton:checked {"
        f"  background: {Colors.OVERLAY_LIGHT_6};"
        f"  color: {Colors.PRIMARY_TEXT};"
        "}"
    )


def spinbox_style() -> str:
    """Generate spinbox stylesheet with modern appearance.

    Returns:
        Complete stylesheet string

    """
    return (
        f"QSpinBox {{"
        f"  background: white;"
        f"  border: 1px solid {Colors.OVERLAY_LIGHT_20};"
        f"  border-radius: {Dimensions.BORDER_RADIUS_SM};"
        f"  padding: 4px 8px;"
        f"  font-size: 13px;"
        f"  color: {Colors.PRIMARY_TEXT};"
        f"  font-family: {Fonts.SYSTEM};"
        f"}}"
        f"QSpinBox:hover {{"
        f"  border-color: {Colors.OVERLAY_LIGHT_30};"
        f"}}"
        f"QSpinBox:focus {{"
        f"  border-color: {Colors.INFO};"
        f"}}"
        f"QSpinBox::up-button, QSpinBox::down-button {{"
        f"  background: transparent;"
        f"  border: none;"
        f"  width: 16px;"
        f"}}"
    )


def combo_box_style(width: int | None = None) -> str:
    """Generate combo box (dropdown) stylesheet.

    Args:
        width: Optional fixed width in pixels

    Returns:
        Complete stylesheet string

    """
    return (
        f"QComboBox {{"
        f"  background: white;"
        f"  border: 1px solid {Colors.OVERLAY_LIGHT_10};"
        f"  border-radius: {Dimensions.BORDER_RADIUS_SM};"
        f"  padding: 4px 8px;"
        f"  font-size: 12px;"
        f"  color: {Colors.PRIMARY_TEXT};"
        f"  font-family: {Fonts.SYSTEM};"
        f"}}"
        f"QComboBox:hover {{"
        f"  border: 1px solid rgba(0, 0, 0, 0.15);"
        f"}}"
        f"QComboBox::drop-down {{"
        f"  border: none;"
        f"  width: 20px;"
        f"}}"
        f"QComboBox QAbstractItemView {{"
        f"  background-color: white;"
        f"  color: {Colors.PRIMARY_TEXT};"
        f"  selection-background-color: {Colors.BUTTON_PRIMARY};"
        f"  selection-color: white;"
        f"  outline: none;"
        f"  border: 1px solid {Colors.OVERLAY_LIGHT_10};"
        f"}}"
    )


def secondary_button_style(
    height: str = Dimensions.BUTTON_HEIGHT_SM,
    align: str = "left",
) -> str:
    """Generate secondary button stylesheet (white background with border).

    Args:
        height: Button height (default: 32px)
        align: Text alignment (default: left)

    Returns:
        Complete stylesheet string

    """
    return (
        f"QPushButton {{"
        f"  background: white;"
        f"  color: {Colors.PRIMARY_TEXT};"
        f"  border: 1px solid {Colors.OVERLAY_LIGHT_10};"
        f"  border-radius: {Dimensions.BORDER_RADIUS_SM};"
        f"  padding: 6px 12px;"
        f"  font-size: 13px;"
        f"  font-weight: 500;"
        f"  text-align: {align};"
        f"  font-family: {Fonts.SYSTEM};"
        f"}}"
        f"QPushButton:hover {{"
        f"  background: {Colors.OVERLAY_LIGHT_6};"
        f"  border: 1px solid rgba(0, 0, 0, 0.15);"
        f"}}"
        f"QPushButton:pressed {{"
        f"  background: {Colors.OVERLAY_LIGHT_10};"
        f"}}"
    )


def segmented_button_style(position: str = "middle") -> str:
    """Generate segmented control button stylesheet (for grouped toggle buttons).

    Args:
        position: Button position - "left", "right", or "middle"

    Returns:
        Complete stylesheet string

    """
    border_radius = ""
    border_style = f"border: 1px solid {Colors.OVERLAY_LIGHT_10};"

    if position == "left":
        border_radius = f"border-top-left-radius: {Dimensions.BORDER_RADIUS_SM};border-bottom-left-radius: {Dimensions.BORDER_RADIUS_SM};"
        border_style = (
            f"border: 1px solid {Colors.OVERLAY_LIGHT_10};border-right: none;"
        )
    elif position == "right":
        border_radius = f"border-top-right-radius: {Dimensions.BORDER_RADIUS_SM};border-bottom-right-radius: {Dimensions.BORDER_RADIUS_SM};"
        border_style = f"border: 1px solid {Colors.OVERLAY_LIGHT_10};"

    return (
        f"QPushButton {{"
        f"  background: white;"
        f"  color: {Colors.SECONDARY_TEXT};"
        f"  {border_style}"
        f"  {border_radius}"
        f"  padding: 4px 16px;"
        f"  font-size: 12px;"
        f"  font-weight: 500;"
        f"  font-family: {Fonts.SYSTEM};"
        f"}}"
        f"QPushButton:checked {{"
        f"  background: {Colors.BUTTON_PRIMARY};"
        f"  color: white;"
        f"}}"
        f"QPushButton:hover:!checked {{"
        f"  background: {Colors.OVERLAY_LIGHT_6};"
        f"}}"
    )


def line_edit_style() -> str:
    """Generate line edit (text input) stylesheet.

    Returns:
        Complete stylesheet string

    """
    return (
        f"QLineEdit {{"
        f"  background: white;"
        f"  border: 1px solid {Colors.OVERLAY_LIGHT_10};"
        f"  border-radius: 4px;"
        f"  padding: 4px 6px;"
        f"  font-size: 12px;"
        f"  color: {Colors.PRIMARY_TEXT};"
        f"  font-family: {Fonts.SYSTEM};"
        f"}}"
        f"QLineEdit:focus {{"
        f"  border: 1px solid {Colors.BUTTON_PRIMARY};"
        f"}}"
        f"QLineEdit:disabled {{"
        f"  background: {Colors.OVERLAY_LIGHT_3};"
        f"  color: {Colors.SECONDARY_TEXT};"
        f"}}"
    )


def divider_style() -> str:
    """Generate horizontal divider stylesheet.

    Returns:
        Complete stylesheet string

    """
    return f"background: {Colors.OVERLAY_LIGHT_10};border: none;"


def group_box_style() -> str:
    """Generate QGroupBox stylesheet used for diagnostics sections.

    Returns:
        Complete stylesheet string

    """
    return (
        "QGroupBox {"
        "  font-size: 14px;"
        "  font-weight: 600;"
        f"  border: 1px solid {Colors.OVERLAY_LIGHT_10};"
        f"  border-radius: {Dimensions.BORDER_RADIUS_MD};"
        "  margin-top: 12px;"
        "  padding-top: 16px;"
        "}"
        "QGroupBox::title {"
        "  subcontrol-origin: margin;"
        "  left: 12px;"
        "  padding: 0 8px;"
        "}"
    )


def text_edit_log_style() -> str:
    """Generate QTextEdit style for log output area.

    Returns:
        Complete stylesheet string

    """
    return (
        "QTextEdit {"
        f"  background: {Colors.BACKGROUND_LIGHT};"
        f"  border: 1px solid {Colors.OVERLAY_LIGHT_10};"
        f"  border-radius: {Dimensions.BORDER_RADIUS_SM};"
        "  padding: 12px;"
        f"  font-family: {Fonts.MONOSPACE};"
        "  font-size: 11px;"
        f"  color: {Colors.PRIMARY_TEXT};"
        "  line-height: 1.4;"
        "}"
    )


# ============================================================================
# MIGRATED FUNCTIONS (from ui/styles.py and utils/ui_styles.py)
# ============================================================================


def get_button_style(variant: str = "standard") -> str:
    """Modern button styles for various button types.

    Args:
        variant: 'standard', 'primary', 'success', 'error', 'text'

    Returns:
        Complete stylesheet string for QPushButton

    """
    variants = {
        "standard": {
            "bg": Colors.OVERLAY_LIGHT_6,
            "hover_bg": Colors.OVERLAY_LIGHT_10,
            "pressed_bg": "rgba(0, 0, 0, 0.14)",
            "text": Colors.PRIMARY_TEXT,
            "border_radius": "8px",
        },
        "primary": {
            "bg": Colors.BUTTON_PRIMARY,
            "hover_bg": Colors.BUTTON_PRIMARY_HOVER,
            "pressed_bg": Colors.BUTTON_PRIMARY_PRESSED,
            "text": "white",
            "border_radius": "8px",
        },
        "success": {
            "bg": Colors.SUCCESS,
            "hover_bg": "#2FB350",
            "pressed_bg": "#28A745",
            "text": "white",
            "border_radius": "8px",
        },
        "error": {
            "bg": Colors.ERROR,
            "hover_bg": "#E6342A",
            "pressed_bg": "#CC2E24",
            "text": "white",
            "border_radius": "8px",
        },
        "text": {
            "bg": "transparent",
            "hover_bg": Colors.OVERLAY_LIGHT_6,
            "pressed_bg": Colors.OVERLAY_LIGHT_10,
            "text": Colors.PRIMARY_TEXT,
            "border_radius": "8px",
        },
    }

    style = variants.get(variant, variants["standard"])

    return f"""
    QPushButton {{
        background: {style['bg']};
        border: none;
        border-radius: {style['border_radius']};
        color: {style['text']};
        padding: 10px 16px;
        font-family: {Fonts.SYSTEM};
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
        color: {Colors.SECONDARY_TEXT};
        opacity: 0.5;
    }}
    """


def get_container_style(elevated: bool = True) -> str:
    """Modern container/surface style with subtle elevation.

    Args:
        elevated: Whether to show elevation with border (Qt doesn't support box-shadow)

    Returns:
        Stylesheet for QFrame/QGroupBox containers

    """
    border = (
        f"border: 2px solid {Colors.OVERLAY_LIGHT_6};"
        if elevated
        else f"border: 1px solid {Colors.OVERLAY_LIGHT_10};"
    )

    return f"""
    QFrame {{
        background-color: {Colors.SURFACE};
        {border}
        border-radius: {Radius.MD}px;
    }}
    """


def get_standard_checkbox_style() -> str:
    """Standard checkbox style with Apple-inspired design.

    Returns:
        Stylesheet for QCheckBox

    """
    return f"""
    QCheckBox {{
        spacing: {Spacing.SM}px;
        font-family: {Fonts.SYSTEM};
        font-size: 9pt;
        color: {Colors.ON_SURFACE};
    }}

    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border-radius: {Radius.SM}px;
        border: 2px solid {Colors.OVERLAY_LIGHT_10};
        background-color: {Colors.SURFACE};
    }}

    QCheckBox::indicator:hover {{
        border-color: {Colors.INFO};
        background-color: {Colors.OVERLAY_LIGHT_6};
    }}

    QCheckBox::indicator:checked {{
        background-color: {Colors.INFO};
        border-color: {Colors.INFO};
    }}

    QCheckBox::indicator:checked:hover {{
        background-color: #0056CC;
    }}

    QCheckBox::indicator:disabled {{
        background-color: {Colors.BACKGROUND_LIGHT};
        border-color: {Colors.OVERLAY_LIGHT_8};
    }}
    """


def get_standard_radiobutton_style() -> str:
    """Standard radio button style with Apple-inspired design.

    Returns:
        Stylesheet for QRadioButton

    """
    return f"""
    QRadioButton {{
        spacing: {Spacing.SM}px;
        font-family: {Fonts.SYSTEM};
        font-size: 9pt;
        color: {Colors.ON_SURFACE};
    }}

    QRadioButton::indicator {{
        width: 18px;
        height: 18px;
        border-radius: 9px;
        border: 2px solid {Colors.OVERLAY_LIGHT_10};
        background-color: {Colors.SURFACE};
    }}

    QRadioButton::indicator:hover {{
        border-color: {Colors.INFO};
        background-color: {Colors.OVERLAY_LIGHT_6};
    }}

    QRadioButton::indicator:checked {{
        background-color: {Colors.INFO};
        border-color: {Colors.INFO};
    }}

    QRadioButton::indicator:checked:hover {{
        background-color: #0056CC;
    }}

    QRadioButton::indicator:disabled {{
        background-color: {Colors.BACKGROUND_LIGHT};
        border-color: {Colors.OVERLAY_LIGHT_8};
    }}
    """


def get_channel_button_style(active_color: str) -> str:
    """Return stylesheet for a checkable channel button with active color.

    Args:
        active_color: Hex color for the checked state background

    Returns:
        Stylesheet for channel toggle button (checked=colored border, unchecked=gray)

    """
    return (
        f"QPushButton {{"
        "  background: white;"
        f"  color: {active_color};"
        f"  border: 2px solid {active_color};"
        "  border-radius: 6px;"
        "  font-size: 12px;"
        "  font-weight: 900;"
        f"  font-family: {Fonts.SYSTEM};"
        "}"
        f"QPushButton:!checked {{"
        "  background: #E5E5E5;"
        "  color: #808080;"
        "  border: 2px solid #808080;"
        "}"
        "QPushButton:hover:!checked {"
        "  border: 2px solid #808080;"
        "}"
    )


def get_channel_button_ref_style(active_color: str) -> str:
    """Return stylesheet for a channel button in reference mode (dotted border).

    Same as get_channel_button_style but with a dotted border to signal
    this channel is the active reference.
    """
    return (
        f"QPushButton {{"
        f"  background: white;"
        f"  color: {active_color};"
        f"  border: 2px dotted {active_color};"
        f"  border-radius: 6px;"
        f"  font-size: 12px;"
        f"  font-weight: 900;"
        f"  font-family: {Fonts.SYSTEM};"
        f"}}"
        f"QPushButton:!checked {{"
        f"  background: #E5E5E5;"
        f"  color: #808080;"
        f"  border: 2px dotted #808080;"
        f"}}"
        f"QPushButton:hover:!checked {{"
        f"  border: 2px dotted #808080;"
        f"}}"
    )


def get_active_cycle_channel_button_style(active_color: str) -> str:
    """Return stylesheet for active cycle graph channel buttons (less curved, more grey).

    Args:
        active_color: Hex color for the checked state background

    Returns:
        Stylesheet for active cycle channel button

    """
    return (
        f"QPushButton {{"
        f"  background: {active_color};"
        "  color: white;"
        "  border: none;"
        "  border-radius: 3px;"
        "  font-size: 12px;"
        "  font-weight: 600;"
        f"  font-family: {Fonts.SYSTEM};"
        "}"
        f"QPushButton:!checked {{"
        f"  background: #E5E5EA;"
        f"  color: {Colors.SECONDARY_TEXT};"
        "}"
        "QPushButton:hover:!checked {"
        f"  background: #D1D1D6;"
        "}"
    )


def get_live_checkbox_style() -> str:
    """Style for the 'Live Data' checkbox in the graphs header.

    Returns:
        Stylesheet for live data checkbox

    """
    return (
        "QCheckBox {"
        "  font-size: 13px;"
        f"  color: {Colors.PRIMARY_TEXT};"
        "  background: transparent;"
        f"  font-family: {Fonts.SYSTEM};"
        "  font-weight: 500;"
        "  spacing: 6px;"
        "}"
        "QCheckBox::indicator {"
        "  width: 18px;"
        "  height: 18px;"
        f"  border: 2px solid {Colors.SECONDARY_TEXT};"
        "  border-radius: 4px;"
        "  background: white;"
        "}"
        "QCheckBox::indicator:checked {"
        f"  background: {Colors.INFO};"
        f"  border-color: {Colors.INFO};"
        "  image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iOSIgdmlld0JveD0iMCAwIDEyIDkiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTEwLjUgMS41TDQgOEwxLjUgNS41IiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIvPjwvc3ZnPg==);"
        "}"
        "QCheckBox::indicator:hover {"
        f"  border-color: {Colors.INFO};"
        "}"
    )


def get_clear_button_style(variant: str = "neutral") -> str:
    """Style for Clear Graph/Flags buttons.

    Args:
        variant: 'neutral' for Clear Graph, 'danger' for Clear Flags

    Returns:
        Stylesheet for clear button

    """
    if variant == "danger":
        return (
            "QPushButton {"
            "  background: rgba(255, 59, 48, 0.1);"
            f"  color: {Colors.ERROR};"
            "  border: 1px solid rgba(255, 59, 48, 0.3);"
            "  border-radius: 6px;"
            "  font-size: 13px;"
            "  font-weight: 500;"
            f"  font-family: {Fonts.SYSTEM};"
            "  padding: 0 16px;"
            "}"
            "QPushButton:hover {"
            "  background: rgba(255, 59, 48, 0.15);"
            "  border: 1px solid rgba(255, 59, 48, 0.5);"
            "}"
            "QPushButton:pressed {"
            "  background: rgba(255, 59, 48, 0.2);"
            "}"
            "QPushButton:disabled {"
            f"  background: {Colors.OVERLAY_LIGHT_3};"
            f"  color: {Colors.SECONDARY_TEXT};"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "}"
            ")"
        )
    else:  # neutral
        return (
            "QPushButton {"
            f"  background: {Colors.OVERLAY_LIGHT_6};"
            f"  color: {Colors.PRIMARY_TEXT};"
            f"  border: 1px solid {Colors.OVERLAY_LIGHT_10};"
            "  border-radius: 6px;"
            "  font-size: 13px;"
            "  font-weight: 500;"
            f"  font-family: {Fonts.SYSTEM};"
            "  padding: 0 16px;"
            "}"
            "QPushButton:hover {"
            f"  background: {Colors.OVERLAY_LIGHT_10};"
            "  border: 1px solid {Colors.OVERLAY_LIGHT_20};"
            "}"
            "QPushButton:pressed {"
            "  background: rgba(0, 0, 0, 0.14);"
            "}"
            "QPushButton:disabled {"
            f"  background: {Colors.OVERLAY_LIGHT_3};"
            f"  color: {Colors.SECONDARY_TEXT};"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "}"
            ")"
        )


# ============================================================================
# CHANNEL COLORS & CHECKBOX STYLES (for sensorgram UI)
# ============================================================================

# Channel visualization colors
CHANNEL_A = "rgb(0, 0, 0)"  # Black
CHANNEL_B = "rgb(255, 0, 81)"  # Red/Pink
CHANNEL_C = "rgb(0, 174, 255)"  # Blue
CHANNEL_D = "rgb(0, 150, 80)"  # Green


def get_font(
    size: int = 9,
    bold: bool = False,
    weight: int = -1,
) -> "QFont":
    """Create a font with specified parameters.

    Args:
        size: Font size in points (default: 9)
        bold: Whether font should be bold
        weight: Explicit font weight (overrides bold if set)

    Returns:
        Configured QFont object

    """
    from PySide6.QtGui import QFont

    font = QFont()
    font.setFamily("Segoe UI")
    font.setPointSize(size)

    if weight != -1:
        font.setWeight(QFont.Weight(weight))
    elif bold:
        font.setBold(True)

    return font


def get_segment_checkbox_font() -> "QFont":
    """Font for segment/channel checkboxes (9pt bold).

    Returns:
        QFont configured for channel checkboxes

    """
    return get_font(size=9, bold=True)


def get_channel_checkbox_style(channel: str, inverted: bool = False) -> str:
    """Channel-specific checkbox style with color coding.

    Args:
        channel: 'A', 'B', 'C', or 'D'
        inverted: If True, use white background with colored text (unchecked)
                 and colored background with white text (checked)

    Returns:
        Stylesheet for channel checkbox

    """
    color_map = {
        "A": CHANNEL_A,
        "B": CHANNEL_B,
        "C": CHANNEL_C,
        "D": CHANNEL_D,
    }

    color = color_map.get(channel.upper(), CHANNEL_A)

    if inverted:
        # Inverted style: white background with channel-colored text normally,
        # colored background with white text when checked
        return f"""
        QCheckBox {{
            color: {color};
            background-color: #FFFFFF;
            border: 2px solid {color};
            border-radius: 6px;
            padding: {Spacing.XS}px;
            font-family: {Fonts.SYSTEM};
            font-size: 9pt;
            font-weight: 900;
        }}
        QCheckBox:checked {{
            background-color: {color};
            color: #FFFFFF;
            border: 2px solid {color};
        }}
        QCheckBox:hover {{
            border: 2px solid {color};
        }}
        """
    else:
        # Original style: colored text on surface background
        return f"""
        QCheckBox {{
            color: {color};
            background-color: {Colors.SURFACE};
            border: 1px solid {Colors.OVERLAY_LIGHT_10};
            border-radius: {Radius.SM}px;
            padding: {Spacing.XS}px;
            font-family: {Fonts.SYSTEM};
            font-size: 9pt;
            font-weight: bold;
        }}
        """


def apply_channel_checkbox_style(checkbox, channel: str, inverted: bool = False) -> None:
    """Apply standard style to a channel checkbox.

    Args:
        checkbox: QCheckBox widget
        channel: 'A', 'B', 'C', or 'D'
        inverted: If True, use inverted style (white bg + colored text)

    """
    checkbox.setFont(get_segment_checkbox_font())
    checkbox.setStyleSheet(get_channel_checkbox_style(channel, inverted=inverted))
