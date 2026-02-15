"""Styled Message Dialogs - Consistent with Calibration UI

Apple HIG-inspired dialogs matching the calibration error state design.
Used for hardware errors, missing devices, and important user notifications.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class StyledMessageDialog(QDialog):
    """Styled message dialog matching calibration UI design.

    Features:
    - Frameless with rounded corners
    - Custom title with color coding (error=red, warning=orange, info=blue)
    - Centered message text
    - Styled buttons matching Apple HIG
    - Semi-transparent parent overlay
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        title: str = "Message",
        message: str = "",
        message_type: str = "error",  # "error", "warning", "info"
        button_text: str = "OK",
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(460)
        self.setMinimumHeight(200)
        self.setMaximumWidth(520)
        self.setMaximumHeight(400)

        # Store parent for overlay
        self.parent_window = parent
        self.overlay = None

        # Create semi-transparent overlay on parent window
        if self.parent_window:
            self.overlay = QWidget(self.parent_window)
            self.overlay.setStyleSheet("background-color: rgba(0, 0, 0, 0.5);")
            self.overlay.setGeometry(self.parent_window.rect())
            self.overlay.show()
            self.overlay.raise_()

        # Frameless window with modern look
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        # Ensure dialog stays on top of overlay
        self.raise_()

        # Style with border and rounded corners
        self.setStyleSheet(
            "QDialog { background: #FFFFFF; border: 3px solid #007AFF; border-radius: 12px; }"
            "QLabel { font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif; color: #1D1D1F; }",
        )

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(12)

        # Title with color based on message type
        title_colors = {
            "error": "#FF3B30",  # Red
            "warning": "#FF9500",  # Orange
            "info": "#007AFF",  # Blue
        }
        title_color = title_colors.get(message_type, "#FF3B30")

        # Add icon prefix based on type
        title_icons = {
            "error": "⚠️ ",
            "warning": "⚠️ ",
            "info": "ℹ️ ",
        }
        title_icon = title_icons.get(message_type, "")

        self.title_label = QLabel(f"{title_icon}{title}")
        self.title_label.setStyleSheet(
            f"font-size: 18px; font-weight: 700; color: {title_color};"
        )
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.title_label)

        # Message
        self.message_label = QLabel(message)
        self.message_label.setStyleSheet(
            "font-size: 14px; color: #1D1D1F; padding: 8px; line-height: 1.4;",
        )
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.message_label.setWordWrap(True)
        self.message_label.setMinimumHeight(60)
        main_layout.addWidget(self.message_label)

        # Spacer
        main_layout.addSpacing(8)

        # Button
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.ok_button = QPushButton(button_text)
        self.ok_button.setFixedSize(120, 36)

        # Button color based on message type
        button_colors = {
            "error": "#FF3B30",  # Red
            "warning": "#FF9500",  # Orange
            "info": "#007AFF",  # Blue
        }
        button_hover_colors = {
            "error": "#E6342A",
            "warning": "#FF8000",
            "info": "#0051D5",
        }
        button_color = button_colors.get(message_type, "#FF3B30")
        button_hover_color = button_hover_colors.get(message_type, "#E6342A")

        self.ok_button.setStyleSheet(
            f"QPushButton {{"
            f"  background: {button_color};"
            f"  color: white;"
            f"  border: none;"
            f"  border-radius: 18px;"
            f"  font-size: 13px;"
            f"  font-weight: 600;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background: {button_hover_color};"
            f"}}"
        )
        self.ok_button.clicked.connect(self._on_accept)
        button_layout.addWidget(self.ok_button)
        button_layout.addStretch()

        main_layout.addLayout(button_layout)

        # Center on parent
        if parent:
            parent_geo = parent.geometry()
            self.move(
                parent_geo.center().x() - self.width() // 2,
                parent_geo.center().y() - self.height() // 2,
            )

        # Ensure dialog is on top after positioning
        self.raise_()
        self.activateWindow()

    def _on_accept(self):
        """Handle OK button click - clean up overlay before accepting."""
        self._cleanup_overlay()
        self.accept()

    def _cleanup_overlay(self):
        """Remove overlay from parent window."""
        if self.overlay:
            self.overlay.hide()
            self.overlay.setParent(None)
            self.overlay.deleteLater()
            self.overlay = None

    def showEvent(self, event):
        """Ensure dialog is on top when shown."""
        super().showEvent(event)
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        """Clean up overlay when closing."""
        self._cleanup_overlay()
        super().closeEvent(event)

    def reject(self):
        """Handle dialog rejection (ESC key, etc) - clean up overlay."""
        self._cleanup_overlay()
        super().reject()


def show_styled_error(parent: QWidget, title: str, message: str) -> None:
    """Show styled error dialog (red).

    Args:
        parent: Parent widget
        title: Dialog title
        message: Error message
    """
    dialog = StyledMessageDialog(
        parent=parent,
        title=title,
        message=message,
        message_type="error",
        button_text="OK",
    )
    dialog.exec()


def show_styled_warning(parent: QWidget, title: str, message: str) -> None:
    """Show styled warning dialog (orange).

    Args:
        parent: Parent widget
        title: Dialog title
        message: Warning message
    """
    dialog = StyledMessageDialog(
        parent=parent,
        title=title,
        message=message,
        message_type="warning",
        button_text="OK",
    )
    dialog.exec()


def show_styled_info(parent: QWidget, title: str, message: str) -> None:
    """Show styled information dialog (blue).

    Args:
        parent: Parent widget
        title: Dialog title
        message: Information message
    """
    dialog = StyledMessageDialog(
        parent=parent,
        title=title,
        message=message,
        message_type="info",
        button_text="OK",
    )
    dialog.exec()
