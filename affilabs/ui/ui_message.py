"""
Lightweight UI message helpers wrapping QMessageBox.

Use these to keep UI messaging consistent and avoid repetitive calls.
"""

from PySide6.QtWidgets import QMessageBox, QWidget


def info(parent, title: str, text: str) -> None:
    # Ensure parent is a QWidget (if it's an Application, get the main window)
    if hasattr(parent, 'main_window'):
        parent = parent.main_window
    elif not isinstance(parent, QWidget):
        parent = None
    QMessageBox.information(parent, title, text)


def warn(parent, title: str, text: str) -> None:
    QMessageBox.warning(parent, title, text)


def error(parent, title: str, text: str) -> None:
    QMessageBox.critical(parent, title, text)


def question(parent, title: str, text: str) -> bool:
    reply = QMessageBox.question(
        parent,
        title,
        text,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    return reply == QMessageBox.StandardButton.Yes
