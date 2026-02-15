"""Lightweight UI message helpers wrapping QMessageBox.

Use these to keep UI messaging consistent and avoid repetitive calls.

All error/warning messages now use styled dialogs matching the calibration UI design
(Apple HIG-inspired with rounded corners, colored titles, and modern buttons).
"""

from PySide6.QtWidgets import QMessageBox, QWidget


def info(parent, title: str, text: str, styled: bool = True) -> None:
    """Show information message.

    Args:
        parent: Parent widget (can be Application or QWidget)
        title: Dialog title
        text: Message text
        styled: Use styled dialog (default True)
    """
    # Ensure parent is a QWidget (if it's an Application, get the main window)
    if hasattr(parent, "main_window"):
        parent = parent.main_window
    elif not isinstance(parent, QWidget):
        parent = None

    if styled:
        from affilabs.widgets.styled_message_dialog import show_styled_info
        show_styled_info(parent, title, text)
    else:
        QMessageBox.information(parent, title, text)


def warn(parent, title: str, text: str, styled: bool = True) -> None:
    """Show warning message.

    Args:
        parent: Parent widget (can be Application or QWidget)
        title: Dialog title
        text: Warning message
        styled: Use styled dialog (default True)
    """
    # Ensure parent is a QWidget (if it's an Application, get the main window)
    if hasattr(parent, "main_window"):
        parent = parent.main_window
    elif not isinstance(parent, QWidget):
        parent = None

    if styled:
        from affilabs.widgets.styled_message_dialog import show_styled_warning
        show_styled_warning(parent, title, text)
    else:
        QMessageBox.warning(parent, title, text)


def error(parent, title: str, text: str, styled: bool = True) -> None:
    """Show error message.

    Args:
        parent: Parent widget (can be Application or QWidget)
        title: Dialog title
        text: Error message
        styled: Use styled dialog (default True)
    """
    # Ensure parent is a QWidget (if it's an Application, get the main window)
    if hasattr(parent, "main_window"):
        parent = parent.main_window
    elif not isinstance(parent, QWidget):
        parent = None

    if styled:
        from affilabs.widgets.styled_message_dialog import show_styled_error
        show_styled_error(parent, title, text)
    else:
        QMessageBox.critical(parent, title, text)


def question(parent, title: str, text: str) -> bool:
    """Show yes/no question dialog.

    Args:
        parent: Parent widget
        title: Dialog title
        text: Question text

    Returns:
        True if user clicked Yes
    """
    # Ensure parent is a QWidget (if it's an Application, get the main window)
    if hasattr(parent, "main_window"):
        parent = parent.main_window
    elif not isinstance(parent, QWidget):
        parent = None

    reply = QMessageBox.question(
        parent,
        title,
        text,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    return reply == QMessageBox.StandardButton.Yes
