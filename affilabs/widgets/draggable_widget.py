"""Draggable Widget System - Make UI elements draggable for layout work."""

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QCursor, QMouseEvent
from PySide6.QtWidgets import QLabel, QWidget


class DraggableWidget(QWidget):
    """Mixin to make any widget draggable during layout work.

    Features:
    - Click and drag to move widget
    - Shows position coordinates while dragging
    - Emits position_changed signal with new coordinates
    - Can be enabled/disabled for production vs layout mode

    Usage:
        widget.enable_dragging()  # Enable drag mode
        widget.disable_dragging()  # Disable drag mode
        widget.position_changed.connect(my_handler)  # Get position updates
    """

    position_changed = Signal(int, int)  # x, y coordinates

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._dragging = False
        self._drag_enabled = False
        self._drag_position = QPoint()
        self._position_label = None

    def enable_dragging(self):
        """Enable dragging mode for this widget."""
        self._drag_enabled = True
        self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))

        # Create position label
        if not self._position_label:
            self._position_label = QLabel(self)
            self._position_label.setStyleSheet(
                "background-color: rgba(46, 48, 227, 200); "
                "color: white; "
                "padding: 4px 8px; "
                "border-radius: 3px; "
                "font-size: 9pt; "
                "font-weight: bold;",
            )
            self._position_label.hide()

    def disable_dragging(self):
        """Disable dragging mode for this widget."""
        self._drag_enabled = False
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        if self._position_label:
            self._position_label.hide()

    def is_dragging_enabled(self) -> bool:
        """Check if dragging is currently enabled."""
        return self._drag_enabled

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press to start dragging."""
        if self._drag_enabled and event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_position = event.globalPosition().toPoint() - self.pos()
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))

            # Show position label
            if self._position_label:
                self._position_label.show()
                self._position_label.raise_()
                self._update_position_label()

            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move to drag widget."""
        if (
            self._drag_enabled
            and self._dragging
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            new_pos = event.globalPosition().toPoint() - self._drag_position
            self.move(new_pos)
            self._update_position_label()
            self.position_changed.emit(new_pos.x(), new_pos.y())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release to end dragging."""
        if self._drag_enabled and event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))

            # Hide position label after a moment
            if self._position_label:
                from PySide6.QtCore import QTimer

                QTimer.singleShot(1000, self._position_label.hide)

            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def _update_position_label(self):
        """Update the position label with current coordinates."""
        if self._position_label:
            pos = self.pos()
            self._position_label.setText(f"x:{pos.x()}, y:{pos.y()}")
            # Position label at top-right of widget
            label_x = self.width() - self._position_label.width() - 10
            label_y = 10
            self._position_label.move(label_x, label_y)


def make_widget_draggable(widget: QWidget) -> QWidget:
    """Convert an existing widget to be draggable by adding the DraggableWidget behavior.

    This is a helper function that dynamically adds drag functionality to a widget.

    Args:
        widget: The widget to make draggable

    Returns:
        The same widget, now with dragging capability

    Usage:
        my_widget = QLabel("Drag me!")
        make_widget_draggable(my_widget)
        my_widget.enable_dragging()

    """
    # Add the dragging methods to the widget's class
    widget.__class__ = type(
        widget.__class__.__name__ + "Draggable",
        (DraggableWidget, widget.__class__),
        {},
    )

    # Initialize dragging attributes
    widget._dragging = False
    widget._drag_enabled = False
    widget._drag_position = QPoint()
    widget._position_label = None

    # Add the signal
    widget.position_changed = Signal(int, int)

    return widget


class LayoutModeManager:
    """Manager to enable/disable layout mode across multiple widgets.

    Usage:
        manager = LayoutModeManager()
        manager.add_widget(my_widget1)
        manager.add_widget(my_widget2)

        manager.enable_layout_mode()  # All widgets become draggable
        manager.disable_layout_mode()  # Back to normal
        manager.print_positions()  # Get code for current positions
    """

    def __init__(self):
        self.widgets = []
        self.widget_names = {}
        self.layout_mode_active = False

    def add_widget(self, widget: QWidget, name: str = None):
        """Add a widget to be managed for layout mode.

        Args:
            widget: Widget to add
            name: Optional name for code generation

        """
        if not isinstance(widget, DraggableWidget):
            # Convert to draggable if needed
            make_widget_draggable(widget)

        self.widgets.append(widget)
        if name:
            self.widget_names[widget] = name
        else:
            self.widget_names[widget] = f"widget_{len(self.widgets)}"

    def enable_layout_mode(self):
        """Enable dragging for all managed widgets."""
        self.layout_mode_active = True
        for widget in self.widgets:
            if isinstance(widget, DraggableWidget):
                widget.enable_dragging()

    def disable_layout_mode(self):
        """Disable dragging for all managed widgets."""
        self.layout_mode_active = False
        for widget in self.widgets:
            if isinstance(widget, DraggableWidget):
                widget.disable_dragging()

    def toggle_layout_mode(self):
        """Toggle layout mode on/off."""
        if self.layout_mode_active:
            self.disable_layout_mode()
        else:
            self.enable_layout_mode()

    def get_positions(self) -> dict:
        """Get current positions of all managed widgets."""
        positions = {}
        for widget in self.widgets:
            name = self.widget_names.get(widget, str(widget))
            pos = widget.pos()
            positions[name] = {"x": pos.x(), "y": pos.y()}
        return positions

    def print_positions(self):
        """Print Python code to set current widget positions."""
        print("\n# Widget positions:")
        for widget in self.widgets:
            name = self.widget_names.get(widget, "widget")
            pos = widget.pos()
            print(f"{name}.move({pos.x()}, {pos.y()})")
        print()

    def save_positions_to_file(self, filepath: str):
        """Save widget positions as Python code to a file."""
        with open(filepath, "w") as f:
            f.write("# Generated widget positions\n\n")
            for widget in self.widgets:
                name = self.widget_names.get(widget, "widget")
                pos = widget.pos()
                f.write(f"{name}.move({pos.x()}, {pos.y()})\n")
