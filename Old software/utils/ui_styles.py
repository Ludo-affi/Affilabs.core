"""Centralized UI styling and theme management for the application.

This module provides a UIStyleManager class that centralizes all UI styling,
making it easy to maintain consistent theming and implement features like
dark mode in the future.

Now using custom modern theme system.
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication


class UIStyleManager:
    """Centralized UI styling and theming manager.

    This class provides all application-wide styling as class methods,
    making it easy to change colors and styles consistently across the
    entire application.
    """

    # Color palette
    COLORS = {
        # Primary backgrounds
        'background_primary': '#D3D3D3',     # Main window background
        'background_secondary': '#C8C8C8',   # GroupBox background
        'background_tertiary': '#E0E0E0',    # Table headers

        # Widget backgrounds
        'widget_background': '#FFFFFF',      # LineEdit, SpinBox, ComboBox, Table
        'button_normal': '#E8E8E8',          # Default button background
        'button_hover': '#F0F0F0',           # Button on hover
        'button_pressed': '#C0C0C0',         # Button when pressed
        'tab_normal': '#C0C0C0',             # Tab background
        'tab_selected': '#D3D3D3',           # Selected tab background
        'tab_hover': '#D0D0D0',              # Tab on hover

        # Selection and highlight colors
        'selection_background': '#B8B8B8',   # Medium gray for selections
        'selection_inactive': '#D8D8D8',     # Gray for inactive selections
        'alternate_row': '#F5F5F5',          # Alternate table row color
        'highlight': '#6B6B6B',              # Dark gray accent for checkboxes, etc.

        # Borders and lines
        'border_primary': '#A0A0A0',         # Standard borders
        'border_secondary': '#C0C0C0',       # Subtle borders (grid lines)

        # Text colors
        'text_primary': '#000000',           # Primary text color
        'text_on_highlight': '#FFFFFF',      # Text on highlighted items
    }

    @classmethod
    def apply_app_theme(cls, app: QApplication) -> None:
        """Apply professional modern theme using custom design system.

        This provides a modern, consistent look with proper hover states,
        focus indicators, and professional styling throughout the app.

        Args:
            app: QApplication instance to apply theme to
        """
        # Use the modern theme from styles package
        try:
            from styles.theme_manager import apply_modern_theme
            apply_modern_theme(app)
        except ImportError:
            # Fallback to basic styling if modern theme not available
            pass

    @classmethod
    def get_main_stylesheet(cls) -> str:
        """Get the complete application-wide stylesheet.

        DEPRECATED: Use apply_app_theme() instead for qt-material styling.
        This method is kept for backwards compatibility only.

        Returns:
            str: Complete CSS stylesheet for the application.
        """
        return f"""
        QMainWindow, QWidget {{
            background-color: {cls.COLORS['background_primary']};
        }}
        QGroupBox {{
            background-color: {cls.COLORS['background_primary']};
            border: 1px solid {cls.COLORS['border_primary']};
            border-radius: 4px;
            margin-top: 0.5em;
            font-weight: bold;
            color: {cls.COLORS['text_primary']};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 3px 0 3px;
            color: {cls.COLORS['text_primary']};
        }}
        QPushButton {{
            background-color: {cls.COLORS['button_normal']};
            border: 1px solid {cls.COLORS['border_primary']};
            border-radius: 3px;
            padding: 5px;
            color: {cls.COLORS['text_primary']};
            font-weight: 500;
        }}
        QPushButton:hover {{
            background-color: {cls.COLORS['button_hover']};
        }}
        QPushButton:pressed {{
            background-color: {cls.COLORS['button_pressed']};
        }}
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
            background-color: {cls.COLORS['widget_background']};
            border: 1px solid {cls.COLORS['border_primary']};
            border-radius: 3px;
            padding: 3px;
            color: {cls.COLORS['text_primary']};
            selection-background-color: {cls.COLORS['selection_background']};
            selection-color: {cls.COLORS['text_primary']};
        }}
        QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
            border: 2px solid {cls.COLORS['highlight']};
        }}
        QComboBox::drop-down {{
            border: none;
            width: 20px;
        }}
        QComboBox::down-arrow {{
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 6px solid {cls.COLORS['text_primary']};
            margin-right: 6px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {cls.COLORS['widget_background']};
            selection-background-color: {cls.COLORS['selection_background']};
            selection-color: {cls.COLORS['text_primary']};
            border: 1px solid {cls.COLORS['border_primary']};
        }}
        QListView {{
            background-color: {cls.COLORS['widget_background']};
            selection-background-color: {cls.COLORS['selection_background']};
            selection-color: {cls.COLORS['text_primary']};
            outline: none;
        }}
        QListView::item:selected {{
            background-color: {cls.COLORS['selection_background']};
            color: {cls.COLORS['text_primary']};
        }}
        QListView::item:hover {{
            background-color: {cls.COLORS['tab_hover']};
        }}
        QTableWidget {{
            background-color: {cls.COLORS['widget_background']};
            alternate-background-color: {cls.COLORS['alternate_row']};
            gridline-color: {cls.COLORS['border_secondary']};
            color: {cls.COLORS['text_primary']};
            selection-background-color: {cls.COLORS['selection_background']};
            selection-color: {cls.COLORS['text_primary']};
        }}
        QTableWidget::item:selected {{
            background-color: {cls.COLORS['selection_background']};
            color: {cls.COLORS['text_primary']};
        }}
        QTableWidget::item:selected:!active {{
            background-color: {cls.COLORS['selection_inactive']};
            color: {cls.COLORS['text_primary']};
        }}
        QHeaderView::section {{
            background-color: {cls.COLORS['background_tertiary']};
            padding: 4px;
            border: 1px solid {cls.COLORS['border_primary']};
            color: {cls.COLORS['text_primary']};
            font-weight: bold;
        }}
        QLabel {{
            color: {cls.COLORS['text_primary']};
            background-color: transparent;
        }}
        QCheckBox {{
            color: {cls.COLORS['text_primary']};
            background-color: transparent;
            spacing: 5px;
        }}
        QCheckBox::indicator {{
            width: 8px;
            height: 8px;
            border: 1px solid {cls.COLORS['border_primary']};
            border-radius: 2px;
            background-color: {cls.COLORS['widget_background']};
        }}
        QCheckBox::indicator:hover {{
            border: 1px solid #707070;
            background-color: #F8F8F8;
        }}
        QCheckBox::indicator:checked {{
            background-color: #4A90E2;
            border: 1px solid #4A90E2;
            image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iOCIgaGVpZ2h0PSI4IiB2aWV3Qm94PSIwIDAgOCA4IiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPjxwYXRoIGQ9Ik0xIDQgTDMgNiBMNyAyIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjEuNSIgZmlsbD0ibm9uZSIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+PC9zdmc+);
        }}
        QRadioButton {{
            color: {cls.COLORS['text_primary']};
            background-color: transparent;
            spacing: 5px;
        }}
        QRadioButton::indicator {{
            width: 8px;
            height: 8px;
            border: 1px solid {cls.COLORS['border_primary']};
            border-radius: 2px;
            background-color: {cls.COLORS['widget_background']};
        }}
        QRadioButton::indicator:hover {{
            border: 1px solid #707070;
            background-color: #F8F8F8;
        }}
        QRadioButton::indicator:checked {{
            background-color: #4A90E2;
            border: 1px solid #4A90E2;
            image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iOCIgaGVpZ2h0PSI4IiB2aWV3Qm94PSIwIDAgOCA4IiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPjxwYXRoIGQ9Ik0xIDQgTDMgNiBMNyAyIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjEuNSIgZmlsbD0ibm9uZSIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+PC9zdmc+);
        }}
        QTabWidget::pane {{
            border: 1px solid {cls.COLORS['border_primary']};
            background-color: {cls.COLORS['background_primary']};
        }}
        QTabBar::tab {{
            background-color: {cls.COLORS['tab_normal']};
            color: {cls.COLORS['text_primary']};
            padding: 6px 12px;
            border: 1px solid {cls.COLORS['border_primary']};
            border-bottom: none;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }}
        QTabBar::tab:selected {{
            background-color: {cls.COLORS['tab_selected']};
            font-weight: bold;
        }}
        QTabBar::tab:hover {{
            background-color: {cls.COLORS['tab_hover']};
        }}
        QFrame {{
            background-color: transparent;
        }}
        QMenu {{
            background-color: {cls.COLORS['widget_background']};
            color: {cls.COLORS['text_primary']};
            border: 1px solid {cls.COLORS['border_primary']};
            padding: 2px;
        }}
        QMenu::item {{
            background-color: transparent;
            color: {cls.COLORS['text_primary']};
            padding: 5px 20px 5px 20px;
        }}
        QMenu::item:selected {{
            background-color: {cls.COLORS['selection_background']};
            color: {cls.COLORS['text_primary']};
        }}
        QMenu::separator {{
            height: 1px;
            background: {cls.COLORS['border_secondary']};
            margin: 4px 0px;
        }}
        QDialog {{
            background-color: {cls.COLORS['background_primary']};
            color: {cls.COLORS['text_primary']};
        }}
        QTreeWidget {{
            background-color: {cls.COLORS['widget_background']};
            color: {cls.COLORS['text_primary']};
            border: 1px solid {cls.COLORS['border_primary']};
            selection-background-color: {cls.COLORS['selection_background']};
            selection-color: {cls.COLORS['text_primary']};
        }}
        QTreeWidget::item:selected {{
            background-color: {cls.COLORS['selection_background']};
            color: {cls.COLORS['text_primary']};
        }}
    """

    @classmethod
    def get_groupbox_style(cls) -> str:
        """Get stylesheet for QGroupBox widgets.

        Returns:
            str: CSS stylesheet for QGroupBox.
        """
        return f"""
            QGroupBox {{
                background-color: {cls.COLORS['background_primary']};
                border: 2px solid {cls.COLORS['border_primary']};
                border-radius: 3px;
            }}
        """

    @classmethod
    def get_button_style(cls) -> str:
        """Get stylesheet for QPushButton widgets.

        Returns:
            str: CSS stylesheet for QPushButton.
        """
        return f"""
            QPushButton {{
                background-color: {cls.COLORS['button_normal']};
                border: 1px solid {cls.COLORS['border_primary']};
                border-radius: 3px;
                padding: 5px;
            }}
            QPushButton:hover {{
                background-color: {cls.COLORS['button_hover']};
            }}
            QPushButton:pressed {{
                background-color: {cls.COLORS['button_pressed']};
            }}
        """

    @classmethod
    def apply_app_theme(cls, app) -> None:
        """Apply the complete application theme to a QApplication.

        Args:
            app: QApplication instance to apply styling to.
        """
        app.setStyleSheet(cls.get_main_stylesheet())
