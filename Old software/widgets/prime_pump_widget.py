from PySide6.QtWidgets import QVBoxLayout, QPushButton, QWidget, QFrame
from PySide6.QtCore import QSize

class PrimePumpWidget(QWidget):
    """Widget for the Prime Pump button, to be placed in the sidebar Flow tab."""
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # Styled container matching Cycle Settings
        container = QFrame(self)
        container.setObjectName("prime_pump_container")
        container.setStyleSheet(
            "QFrame#prime_pump_container {"
            "    background-color: white;"
            "    border: 1px solid rgb(180, 180, 180);"
            "    border-radius: 8px;"
            "}"
        )
        container.setFrameShape(QFrame.StyledPanel)
        container.setFrameShadow(QFrame.Raised)
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(12, 12, 12, 12)
        container_layout.setSpacing(8)

        self.prime_btn = QPushButton("Prime Pumps", container)
        self.prime_btn.setMinimumSize(QSize(0, 35))
        self.prime_btn.setObjectName("prime_btn")
        self.prime_btn.setStyleSheet(
            "QPushButton {"
            "    background-color: rgb(46, 48, 227);"
            "    color: white;"
            "    border: 1px solid rgb(46, 48, 227);"
            "    border-radius: 4px;"
            "    font-weight: bold;"
            "    padding: 8px;"
            "}"
            "QPushButton:hover {"
            "    background-color: rgb(66, 68, 247);"
            "}"
            "QPushButton:pressed {"
            "    background-color: rgb(26, 28, 207);"
            "}"
        )
        container_layout.addWidget(self.prime_btn)
        layout.addWidget(container)

    def set_prime_callback(self, callback):
        self.prime_btn.clicked.connect(callback)
