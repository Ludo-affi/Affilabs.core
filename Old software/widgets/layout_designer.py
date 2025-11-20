"""UI Layout Designer Mode - Interactive drag-and-drop UI editing."""

from PySide6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QDialog, QTextEdit, QDialogButtonBox, QGroupBox, QSpinBox
)
from PySide6.QtCore import Qt, Signal, QPoint, QRect
from PySide6.QtGui import QPainter, QPen, QColor, QFont


class DraggableWidget(QFrame):
    """Wrapper that makes any widget draggable and shows position info."""

    position_changed = Signal(QPoint)

    def __init__(self, widget, name="Widget", parent=None):
        super().__init__(parent)
        self.wrapped_widget = widget
        self.widget_name = name
        self.dragging = False
        self.drag_start_pos = QPoint()

        # Setup frame
        self.setFrameShape(QFrame.Shape.Box)
        self.setLineWidth(2)
        self.setStyleSheet("QFrame { border: 2px dashed rgb(46, 48, 227); background: transparent; }")

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        # Label showing widget info
        self.info_label = QLabel(f"{name}")
        self.info_label.setStyleSheet(
            "background: rgb(46, 48, 227); color: white; "
            "padding: 2px 5px; font-size: 8pt; font-weight: bold;"
        )
        layout.addWidget(self.info_label)

        # The actual widget
        layout.addWidget(widget)

        # Enable mouse tracking
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.SizeAllCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.drag_start_pos = event.position().toPoint()
            self.setStyleSheet("QFrame { border: 2px solid rgb(255, 0, 0); background: rgba(46, 48, 227, 0.1); }")

    def mouseMoveEvent(self, event):
        if self.dragging:
            delta = event.position().toPoint() - self.drag_start_pos
            new_pos = self.pos() + delta
            self.move(new_pos)
            self.info_label.setText(f"{self.widget_name} - X:{new_pos.x()} Y:{new_pos.y()}")
            self.position_changed.emit(new_pos)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            self.setStyleSheet("QFrame { border: 2px dashed rgb(46, 48, 227); background: transparent; }")


class ResizableWidget(QFrame):
    """Wrapper that makes widgets resizable with corner handles."""

    size_changed = Signal(QRect)

    def __init__(self, widget, name="Widget", parent=None):
        super().__init__(parent)
        self.wrapped_widget = widget
        self.widget_name = name
        self.resizing = False
        self.resize_start_pos = QPoint()
        self.resize_start_size = self.size()

        # Setup frame
        self.setFrameShape(QFrame.Shape.Box)
        self.setLineWidth(2)
        self.setStyleSheet("QFrame { border: 2px dashed rgb(46, 227, 111); background: transparent; }")

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        # Label
        self.info_label = QLabel(f"{name} - {widget.width()}x{widget.height()}")
        self.info_label.setStyleSheet(
            "background: rgb(46, 227, 111); color: black; "
            "padding: 2px 5px; font-size: 8pt; font-weight: bold;"
        )
        layout.addWidget(self.info_label)

        # The widget
        layout.addWidget(widget)

        # Resize handle
        self.resize_handle = QLabel("◢")
        self.resize_handle.setFixedSize(16, 16)
        self.resize_handle.setStyleSheet(
            "QLabel { background: rgb(46, 227, 111); color: white; "
            "font-size: 12pt; padding: 0; margin: 0; }"
        )
        self.resize_handle.setCursor(Qt.CursorShape.SizeFDiagCursor)
        layout.addWidget(self.resize_handle, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)

        self.setMouseTracking(True)


class LayoutDesignPanel(QWidget):
    """Control panel for layout design mode."""

    toggle_design_mode = Signal(bool)
    generate_code = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.design_mode_active = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Title
        title = QLabel("🎨 UI Layout Designer")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # Instructions
        instructions = QLabel(
            "Click 'Enable Design Mode' to make UI elements draggable.\n"
            "Drag elements to reposition them.\n"
            "Click 'Generate Code' to save changes."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("color: rgb(100, 100, 100); font-size: 9pt; padding: 5px;")
        layout.addWidget(instructions)

        # Toggle button
        self.toggle_btn = QPushButton("Enable Design Mode")
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: rgb(46, 48, 227);
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:checked {
                background-color: rgb(227, 48, 46);
            }
            QPushButton:hover {
                background-color: rgb(66, 68, 247);
            }
            QPushButton:checked:hover {
                background-color: rgb(247, 68, 66);
            }
        """)
        self.toggle_btn.toggled.connect(self._on_toggle)
        layout.addWidget(self.toggle_btn)

        # Generate code button
        self.generate_btn = QPushButton("📝 Generate Code")
        self.generate_btn.setEnabled(False)
        self.generate_btn.setStyleSheet("""
            QPushButton {
                background-color: rgb(46, 227, 111);
                color: black;
                border: none;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:disabled {
                background-color: rgb(200, 200, 200);
                color: rgb(150, 150, 150);
            }
            QPushButton:hover:!disabled {
                background-color: rgb(66, 247, 131);
            }
        """)
        self.generate_btn.clicked.connect(self.generate_code.emit)
        layout.addWidget(self.generate_btn)

        # Quick adjustments group
        adjust_group = QGroupBox("Quick Adjustments")
        adjust_layout = QVBoxLayout(adjust_group)

        # Device Status size
        device_layout = QHBoxLayout()
        device_layout.addWidget(QLabel("Device Status Height:"))
        self.device_height_spin = QSpinBox()
        self.device_height_spin.setRange(200, 800)
        self.device_height_spin.setValue(400)
        self.device_height_spin.setSuffix(" px")
        device_layout.addWidget(self.device_height_spin)
        adjust_layout.addLayout(device_layout)

        # Sidebar width
        sidebar_layout = QHBoxLayout()
        sidebar_layout.addWidget(QLabel("Sidebar Width:"))
        self.sidebar_width_spin = QSpinBox()
        self.sidebar_width_spin.setRange(250, 500)
        self.sidebar_width_spin.setValue(340)
        self.sidebar_width_spin.setSuffix(" px")
        sidebar_layout.addWidget(self.sidebar_width_spin)
        adjust_layout.addLayout(sidebar_layout)

        layout.addWidget(adjust_group)

        layout.addStretch()

    def _on_toggle(self, checked):
        self.design_mode_active = checked
        if checked:
            self.toggle_btn.setText("🔴 Disable Design Mode")
            self.generate_btn.setEnabled(True)
        else:
            self.toggle_btn.setText("Enable Design Mode")
            self.generate_btn.setEnabled(False)

        self.toggle_design_mode.emit(checked)


class CodeGeneratorDialog(QDialog):
    """Dialog showing generated code for current layout."""

    def __init__(self, code_snippets: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Generated Layout Code")
        self.setModal(False)
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setMinimumSize(600, 500)

        layout = QVBoxLayout(self)

        # Title
        title = QLabel("📝 Copy this code to apply your layout changes:")
        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # Instructions
        instructions = QLabel(
            "Copy the code below and paste it into your __init__ or setup methods.\n"
            "The code sets exact positions and sizes based on your adjustments."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("color: rgb(100, 100, 100); padding: 5px;")
        layout.addWidget(instructions)

        # Code display
        self.code_text = QTextEdit()
        self.code_text.setReadOnly(True)
        self.code_text.setStyleSheet("""
            QTextEdit {
                background-color: rgb(30, 30, 30);
                color: rgb(220, 220, 220);
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 10pt;
                padding: 10px;
                border: 1px solid rgb(100, 100, 100);
            }
        """)

        # Generate code text
        code = self._generate_code(code_snippets)
        self.code_text.setPlainText(code)

        layout.addWidget(self.code_text)

        # Buttons
        button_box = QDialogButtonBox()
        copy_btn = QPushButton("📋 Copy to Clipboard")
        copy_btn.clicked.connect(self._copy_to_clipboard)
        button_box.addButton(copy_btn, QDialogButtonBox.ButtonRole.ActionRole)
        button_box.addButton(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.close)
        layout.addWidget(button_box)

    def _generate_code(self, snippets: dict) -> str:
        """Generate formatted Python code from snippets."""
        code_lines = [
            "# Generated Layout Code",
            "# Paste this into your widget's __init__ or setup method",
            "",
        ]

        for widget_name, props in snippets.items():
            code_lines.append(f"# {widget_name}")
            if 'x' in props and 'y' in props:
                code_lines.append(f"self.{widget_name}.move({props['x']}, {props['y']})")
            if 'width' in props and 'height' in props:
                code_lines.append(f"self.{widget_name}.setFixedSize({props['width']}, {props['height']})")
            if 'min_width' in props:
                code_lines.append(f"self.{widget_name}.setMinimumWidth({props['min_width']})")
            if 'min_height' in props:
                code_lines.append(f"self.{widget_name}.setMinimumHeight({props['min_height']})")
            code_lines.append("")

        return "\n".join(code_lines)

    def _copy_to_clipboard(self):
        """Copy code to clipboard."""
        from PySide6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(self.code_text.toPlainText())

        # Visual feedback
        original_text = self.sender().text()
        self.sender().setText("✅ Copied!")
        from PySide6.QtCore import QTimer
        QTimer.singleShot(2000, lambda: self.sender().setText(original_text))


# Quick helper functions for common UI adjustments

def make_widget_draggable(widget, name="Widget"):
    """Wrap a widget to make it draggable in design mode."""
    return DraggableWidget(widget, name)


def make_widget_resizable(widget, name="Widget"):
    """Wrap a widget to make it resizable in design mode."""
    return ResizableWidget(widget, name)


def get_layout_code(widget_positions: dict) -> str:
    """
    Generate Python code for widget positions.

    Args:
        widget_positions: Dict like {'widget_name': {'x': 10, 'y': 20, 'width': 300, 'height': 200}}

    Returns:
        Python code string
    """
    dialog = CodeGeneratorDialog(widget_positions)
    return dialog.code_text.toPlainText()
