from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import QLineEdit, QStyledItemDelegate


class NumericDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = super().createEditor(parent, option, index)
        if isinstance(editor, QLineEdit):
            reg_ex = QRegularExpression("[-]?([0-9]*[.])?[0-9]+")
            validator = QRegularExpressionValidator(reg_ex, editor)
            editor.setValidator(validator)
        return editor
