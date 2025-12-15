"""Custom delegates for table cell editing."""

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QLineEdit, QStyledItemDelegate

from widgets.ui_constants import CYCLE_TYPES

logger = logging.getLogger(__name__)


class CycleTypeDelegate(QStyledItemDelegate):
    """Delegate to provide a dropdown for cycle type selection."""

    def createEditor(self, parent, option, index):
        """Create a QComboBox editor."""
        combo = QComboBox(parent)
        combo.addItems(CYCLE_TYPES)
        # Style the combobox to ensure text is visible
        combo.setStyleSheet("""
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
        """)
        return combo

    def setEditorData(self, editor, index):
        """Set the current value in the combo box."""
        current_text = index.data()
        if current_text in CYCLE_TYPES:
            editor.setCurrentText(current_text)
        else:
            editor.setCurrentIndex(0)

    def setModelData(self, editor, model, index):
        """Save the selected value back to the model."""
        model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)


class TextInputDelegate(QStyledItemDelegate):
    """Delegate for text input with character limits and validation."""

    # Character limits for different column types
    NAME_LIMIT = 50
    NOTE_LIMIT = 500

    def createEditor(self, parent, option, index):
        """Create a line edit with character limit."""
        editor = QLineEdit(parent)

        # Set character limit based on column
        column = index.column()
        if column == 0:  # Name column
            editor.setMaxLength(self.NAME_LIMIT)
            editor.setPlaceholderText(f"Max {self.NAME_LIMIT} characters")
        elif column == 9:  # Note column
            editor.setMaxLength(self.NOTE_LIMIT)
            editor.setPlaceholderText(f"Max {self.NOTE_LIMIT} characters")
        else:
            editor.setMaxLength(100)  # Default limit for other text columns

        return editor

    def setEditorData(self, editor, index):
        """Set current value in editor with safety checks."""
        try:
            current_text = index.data()
            if current_text is not None:
                editor.setText(str(current_text))
            else:
                editor.setText("")
        except Exception as e:
            logger.warning(f"Error setting editor data: {e}")
            editor.setText("")

    def setModelData(self, editor, model, index):
        """Save value back to model with validation."""
        try:
            text = editor.text().strip()
            # Additional validation: remove any problematic characters
            text = text.replace("\x00", "")  # Remove null bytes
            text = "".join(
                char for char in text if ord(char) >= 32 or char in "\n\r\t"
            )  # Keep printable chars
            model.setData(index, text, Qt.ItemDataRole.EditRole)
        except Exception as e:
            logger.error(f"Error saving table cell data: {e}")
            # Don't crash - just log the error
