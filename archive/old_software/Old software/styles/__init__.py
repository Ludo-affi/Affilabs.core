"""Modern UI Styling Package
Professional theme system for SPR instrument software
"""

from .design_system import *
from .graph_styling import (
    apply_modern_graph_style,
    create_channel_pens,
    create_modern_pen,
    get_cursor_style,
    get_graph_colors,
    get_modern_plot_style,
    style_plot_widget,
)
from .theme_manager import (
    ThemeManager,
    apply_modern_theme,
    get_color,
    get_theme_manager,
    set_card_style,
    set_danger_button_style,
    set_primary_button_style,
    set_secondary_button_style,
    set_success_button_style,
    set_toolbar_style,
)

__all__ = [
    # Design system constants
    "PRIMARY",
    "SUCCESS",
    "WARNING",
    "ERROR",
    "INFO",
    "BACKGROUND",
    "SURFACE",
    "TEXT_PRIMARY",
    "TEXT_SECONDARY",
    "CHANNEL_A",
    "CHANNEL_B",
    "CHANNEL_C",
    "CHANNEL_D",
    # Theme management
    "ThemeManager",
    "get_theme_manager",
    "apply_modern_theme",
    "get_color",
    # Widget styling functions
    "set_primary_button_style",
    "set_secondary_button_style",
    "set_success_button_style",
    "set_danger_button_style",
    "set_card_style",
    "set_toolbar_style",
    # Graph styling
    "apply_modern_graph_style",
    "get_modern_plot_style",
    "create_modern_pen",
    "create_channel_pens",
    "get_cursor_style",
    "style_plot_widget",
    "get_graph_colors",
]

__version__ = "1.0.0"
