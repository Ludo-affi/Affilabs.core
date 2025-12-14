"""Collapsible/Expandable box widget for organizing controls."""

from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtWidgets import QWidget, QVBoxLayout, QToolButton, QFrame, QScrollArea, QSizePolicy


class CollapsibleBox(QWidget):
    """A collapsible box widget with a toggle button and content area."""

    def __init__(self, title="", parent=None):
        """Initialize the collapsible box.

        Args:
            title: The title text to display on the toggle button
            parent: Parent widget
        """
        super().__init__(parent)

        self.toggle_button = QToolButton(self)
        self.toggle_button.setText(title)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(True)
        self.toggle_button.setStyleSheet("""
            QToolButton {
                border: none;
                background-color: rgb(220, 220, 220);
                padding: 8px;
                text-align: left;
                font-weight: bold;
                font-size: 10pt;
            }
            QToolButton:hover {
                background-color: rgb(210, 210, 210);
            }
            QToolButton:checked {
                background-color: rgb(200, 200, 200);
            }
        """)
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle_button.setArrowType(Qt.ArrowType.DownArrow)
        self.toggle_button.clicked.connect(self.toggle)

        self.content_area = QScrollArea(self)
        self.content_area.setMaximumHeight(0)
        self.content_area.setMinimumHeight(0)
        self.content_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.content_area.setFrameShape(QFrame.Shape.NoFrame)
        self.content_area.setWidgetResizable(True)

        # Create a container widget for the content
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(5, 5, 5, 5)
        self.content_layout.setSpacing(5)
        self.content_area.setWidget(self.content_widget)

        # Animation for expanding/collapsing
        self.toggle_animation = QPropertyAnimation(self.content_area, b"maximumHeight")
        self.toggle_animation.setDuration(300)
        self.toggle_animation.setEasingCurve(QEasingCurve.Type.InOutQuart)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.toggle_button)
        main_layout.addWidget(self.content_area)

        # Start expanded by default
        self.content_area.setMaximumHeight(16777215)

    def toggle(self):
        """Toggle the expansion state of the box."""
        checked = self.toggle_button.isChecked()
        arrow_type = Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow
        self.toggle_button.setArrowType(arrow_type)

        if checked:
            # Expand
            content_height = self.content_widget.sizeHint().height()
            self.toggle_animation.setStartValue(0)
            self.toggle_animation.setEndValue(content_height)
        else:
            # Collapse
            self.toggle_animation.setStartValue(self.content_area.maximumHeight())
            self.toggle_animation.setEndValue(0)

        self.toggle_animation.start()

    def add_widget(self, widget):
        """Add a widget to the content area.

        Args:
            widget: The widget to add to the content area
        """
        self.content_layout.addWidget(widget)

    def add_layout(self, layout):
        """Add a layout to the content area.

        Args:
            layout: The layout to add to the content area
        """
        self.content_layout.addLayout(layout)

    def set_expanded(self, expanded):
        """Set the expansion state programmatically.

        Args:
            expanded: True to expand, False to collapse
        """
        if expanded != self.toggle_button.isChecked():
            self.toggle_button.setChecked(expanded)
            self.toggle()
