"""
Professional Theme Manager using qt-material library
Combines qt-material's polished Material Design with custom ezControl branding
"""

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor
from qt_material import apply_stylesheet, list_themes
from pathlib import Path
import json


class ThemeManager:
    """Manages application theming using qt-material library"""

    # Available qt-material themes
    LIGHT_THEMES = [
        'light_blue.xml',
        'light_cyan.xml',
        'light_lightgreen.xml',
        'light_pink.xml',
        'light_purple.xml',
        'light_teal.xml',
    ]

    DARK_THEMES = [
        'dark_blue.xml',
        'dark_cyan.xml',
        'dark_lightgreen.xml',
        'dark_pink.xml',
        'dark_purple.xml',
        'dark_teal.xml',
    ]

    # ezControl custom theme (light blue matching company colors)
    EZCONTROL_THEME = 'light_blue.xml'

    @staticmethod
    def apply_theme(app: QApplication, theme_name: str = None, custom_colors: dict = None):
        """
        Apply qt-material theme to the application

        Args:
            app: QApplication instance
            theme_name: Name of theme (default: light_blue.xml)
            custom_colors: Optional dict to override specific colors
                Example: {'primaryColor': '#2E30E3', 'primaryLightColor': '#5254FF'}
        """
        if theme_name is None:
            theme_name = ThemeManager.EZCONTROL_THEME

        # Apply base qt-material theme
        apply_stylesheet(app, theme=theme_name)

        # Override with custom ezControl colors if provided
        if custom_colors:
            stylesheet = app.styleSheet()

            # Inject custom color variables
            custom_css = "\n/* ezControl Custom Colors */\n"
            for key, value in custom_colors.items():
                custom_css += f"* {{ --{key}: {value}; }}\n"

            app.setStyleSheet(stylesheet + custom_css)

    @staticmethod
    def apply_ezcontrol_theme(app: QApplication):
        """
        Apply ezControl's custom branded theme
        Uses light_blue.xml as base with company colors
        """
        custom_colors = {
            'primaryColor': '#2E30E3',        # ezControl blue
            'primaryLightColor': '#5254FF',   # Lighter blue
            'secondaryColor': '#FF0051',      # Channel B pink/red
            'secondaryLightColor': '#FF3377',
            'primaryTextColor': '#1C1C1E',    # Dark text
            'secondaryTextColor': '#46464A',  # Grey text
        }

        ThemeManager.apply_theme(app, ThemeManager.EZCONTROL_THEME, custom_colors)

    @staticmethod
    def get_available_themes() -> dict:
        """Get all available qt-material themes"""
        return {
            'light': ThemeManager.LIGHT_THEMES,
            'dark': ThemeManager.DARK_THEMES
        }

    @staticmethod
    def list_all_themes():
        """Print all available themes (debug helper)"""
        print("Available qt-material themes:")
        for theme in list_themes():
            print(f"  - {theme}")


# Quick access function for main.py
def setup_app_theme(app: QApplication):
    """
    One-line setup for main.py
    Applies professional Material Design theme to entire app
    """
    ThemeManager.apply_ezcontrol_theme(app)
    print("✓ Professional Material Design theme applied")
