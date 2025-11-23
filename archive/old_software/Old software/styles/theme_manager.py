"""
Theme Loader & Manager
Loads and applies modern theme to the application
"""

from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QPalette, QColor
from PySide6.QtCore import Qt
import pyqtgraph as pg

# Import design system
try:
    from styles.design_system import *
    from styles.graph_styling import apply_modern_graph_style
except ImportError:
    # Fallback for different import contexts
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    from design_system import *
    from graph_styling import apply_modern_graph_style


class ThemeManager:
    """Manages application theming."""

    def __init__(self):
        self.theme_dir = Path(__file__).parent
        self.current_theme = "modern"

    def load_qss(self, qss_file="modern_theme.qss"):
        """Load QSS stylesheet file."""
        qss_path = self.theme_dir / qss_file
        if qss_path.exists():
            with open(qss_path, 'r', encoding='utf-8') as f:
                return f.read()
        return ""

    def apply_theme(self, app: QApplication, theme="modern"):
        """Apply complete theme to application."""
        self.current_theme = theme

        # 1. Load and apply QSS stylesheet
        qss = self.load_qss(f"{theme}_theme.qss")
        if qss:
            app.setStyleSheet(qss)

        # 2. Set application font
        font = QFont(FONT_FAMILY.split(',')[0].strip("'"))
        font.setPointSize(int(FONT_BASE.replace('px', '')) * 0.75)  # Convert px to pt
        app.setFont(font)

        # 3. Apply PyQtGraph styling
        apply_modern_graph_style()

        # 4. Set palette for better native widget rendering
        self._apply_palette(app)

        return True

    def _apply_palette(self, app: QApplication):
        """Apply color palette to application."""
        palette = QPalette()

        # Window colors
        palette.setColor(QPalette.ColorRole.Window, QColor(BACKGROUND))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT_PRIMARY))

        # Base colors (for input widgets)
        palette.setColor(QPalette.ColorRole.Base, QColor(SURFACE))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(SURFACE_ELEVATED))

        # Text colors
        palette.setColor(QPalette.ColorRole.Text, QColor(TEXT_PRIMARY))
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(TEXT_TERTIARY))

        # Button colors
        palette.setColor(QPalette.ColorRole.Button, QColor(PRIMARY))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT_INVERSE))

        # Highlight colors (selections)
        palette.setColor(QPalette.ColorRole.Highlight, QColor(PRIMARY))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(TEXT_INVERSE))

        # Disabled state
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(TEXT_DISABLED))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(TEXT_DISABLED))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(TEXT_DISABLED))

        app.setPalette(palette)

    def get_color(self, color_name):
        """Get color from design system by name."""
        color_map = {
            'primary': PRIMARY,
            'success': SUCCESS,
            'warning': WARNING,
            'error': ERROR,
            'info': INFO,
            'background': BACKGROUND,
            'surface': SURFACE,
            'text_primary': TEXT_PRIMARY,
            'text_secondary': TEXT_SECONDARY,
            'channel_a': CHANNEL_A,
            'channel_b': CHANNEL_B,
            'channel_c': CHANNEL_C,
            'channel_d': CHANNEL_D,
        }
        return color_map.get(color_name, TEXT_PRIMARY)


# Global theme manager instance
_theme_manager = None

def get_theme_manager() -> ThemeManager:
    """Get or create global theme manager instance."""
    global _theme_manager
    if _theme_manager is None:
        _theme_manager = ThemeManager()
    return _theme_manager


def apply_modern_theme(app: QApplication):
    """Convenience function to apply modern theme."""
    manager = get_theme_manager()
    return manager.apply_theme(app, "modern")


def get_color(color_name):
    """Convenience function to get a color."""
    manager = get_theme_manager()
    return manager.get_color(color_name)


# Quick style classes for widgets
def set_primary_button_style(button):
    """Apply primary button styling."""
    button.setProperty("class", "primary")
    button.style().unpolish(button)
    button.style().polish(button)


def set_secondary_button_style(button):
    """Apply secondary button styling."""
    button.setProperty("class", "secondary")
    button.style().unpolish(button)
    button.style().polish(button)


def set_success_button_style(button):
    """Apply success button styling."""
    button.setProperty("class", "success")
    button.style().unpolish(button)
    button.style().polish(button)


def set_danger_button_style(button):
    """Apply danger button styling."""
    button.setProperty("class", "danger")
    button.style().unpolish(button)
    button.style().polish(button)


def set_card_style(widget):
    """Apply card styling to a frame/widget."""
    widget.setProperty("class", "card")
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def set_toolbar_style(widget):
    """Apply toolbar styling."""
    widget.setProperty("class", "toolbar")
    widget.style().unpolish(widget)
    widget.style().polish(widget)


if __name__ == "__main__":
    print("Theme Manager Ready ✓")
    print(f"Theme Directory: {Path(__file__).parent}")
    print(f"Primary Color: {PRIMARY}")
    print(f"Available themes: modern")
