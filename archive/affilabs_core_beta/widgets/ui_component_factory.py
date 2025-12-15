"""UI Component Factory

Provides factory methods for creating consistently styled UI components.
Eliminates duplication of styling code across multiple UI files.
"""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QLabel, QWidget

from widgets.ui_constants import CycleConfig


class UIComponentFactory:
    """Factory for creating styled UI components with consistent appearance."""

    # Standard ComboBox stylesheet for cycle controls
    COMBOBOX_STYLE = """
        QComboBox {
            background-color: white;
            color: black;
            border: 1px solid gray;
            padding: 2px;
        }
        QComboBox:hover {
            background-color: #f0f0f0;
        }
        QComboBox::drop-down {
            border: none;
        }
        QComboBox QAbstractItemView {
            background-color: white;
            color: black;
            selection-background-color: #0078d4;
            selection-color: white;
        }
    """

    @classmethod
    def create_cycle_type_dropdown(
        cls,
        parent: QWidget | None = None,
        object_name: str = "current_cycle_type",
    ) -> QComboBox:
        """Create a styled cycle type dropdown.

        Args:
            parent: Parent widget
            object_name: Qt object name for the widget

        Returns:
            Configured QComboBox with cycle types

        """
        combo = QComboBox(parent)
        combo.setObjectName(object_name)
        combo.addItems(CycleConfig.TYPES)
        combo.setStyleSheet(cls.COMBOBOX_STYLE)
        return combo

    @classmethod
    def create_cycle_time_dropdown(
        cls,
        parent: QWidget | None = None,
        object_name: str = "current_cycle_time",
        enabled: bool = False,
    ) -> QComboBox:
        """Create a styled cycle time dropdown.

        Args:
            parent: Parent widget
            object_name: Qt object name for the widget
            enabled: Whether dropdown should be initially enabled

        Returns:
            Configured QComboBox with cycle time options

        """
        combo = QComboBox(parent)
        combo.setObjectName(object_name)
        # Format time options as "X min"
        time_items = [f"{minutes} min" for minutes in CycleConfig.TIME_OPTIONS]
        combo.addItems(time_items)
        combo.setStyleSheet(cls.COMBOBOX_STYLE)
        combo.setEnabled(enabled)
        return combo

    @classmethod
    def create_label(
        cls,
        text: str,
        parent: QWidget | None = None,
        object_name: str | None = None,
    ) -> QLabel:
        """Create a styled label for UI controls.

        Args:
            text: Label text
            parent: Parent widget
            object_name: Qt object name for the widget

        Returns:
            Configured QLabel

        """
        label = QLabel(parent)
        if object_name:
            label.setObjectName(object_name)
        label.setText(text)
        # Could apply UIStyle.LABEL_STYLE here if needed
        return label

    @classmethod
    def create_styled_combobox(
        cls,
        items: list[str],
        parent: QWidget | None = None,
        object_name: str | None = None,
        style: str | None = None,
    ) -> QComboBox:
        """Create a generic styled combobox.

        Args:
            items: List of items for the dropdown
            parent: Parent widget
            object_name: Qt object name for the widget
            style: Custom stylesheet (uses default if None)

        Returns:
            Configured QComboBox

        """
        combo = QComboBox(parent)
        if object_name:
            combo.setObjectName(object_name)
        combo.addItems(items)
        combo.setStyleSheet(style or cls.COMBOBOX_STYLE)
        return combo
