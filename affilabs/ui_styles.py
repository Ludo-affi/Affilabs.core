"""UI Stylesheet Constants and Style Builders
Centralized styling for consistent UI appearance across the application.
"""
from __future__ import annotations


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
        "  padding: 10px 12px;"
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
