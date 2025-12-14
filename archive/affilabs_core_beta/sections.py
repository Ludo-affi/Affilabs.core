"""Reusable UI section components extracted from LL_UI_v1_0.py."""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton
from ui_styles import collapsible_header_style

class CollapsibleSection(QWidget):
    """A collapsible section widget with header and content."""

    def __init__(self, title: str, parent=None, is_expanded: bool = True):
        super().__init__(parent)
        self.is_expanded = is_expanded

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.header_btn = QPushButton(f"{'▼' if is_expanded else '▶'} {title}")
        self.header_btn.setCheckable(True)
        self.header_btn.setChecked(is_expanded)
        self.header_btn.setStyleSheet(collapsible_header_style())
        self.header_btn.clicked.connect(self.toggle)
        main_layout.addWidget(self.header_btn)

        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 8, 0, 0)
        self.content_layout.setSpacing(8)
        main_layout.addWidget(self.content_widget)

        self.content_widget.setVisible(is_expanded)

    def toggle(self):
        self.is_expanded = not self.is_expanded
        title_text = self.header_btn.text()[2:]
        self.header_btn.setText(f"{'▼' if self.is_expanded else '▶'} {title_text}")
        self.content_widget.setVisible(self.is_expanded)

    def add_content_widget(self, widget):
        self.content_layout.addWidget(widget)

    def add_content_layout(self, layout):
        self.content_layout.addLayout(layout)
