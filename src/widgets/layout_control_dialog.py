"""Reusable Layout Control Dialog - Nimble, non-modal dialog for adjusting UI elements."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QSpinBox, QGroupBox, QDialogButtonBox, QCheckBox
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QGuiApplication


class LayoutControlDialog(QDialog):
    """
    Nimble, non-modal dialog for live UI layout adjustments.

    Features:
    - Non-modal: Can interact with main UI while open
    - Real-time updates: Changes apply as you adjust controls
    - Revertible: Cancel button restores original state
    - Tool window: Stays on top, compact design

    Usage:
        1. Subclass this dialog
        2. Override _setup_controls() to add your specific controls
        3. Override get_values() to return current control values
        4. Override _load_values() to set control values from dict
        5. Connect values_changed signal to your update method
    """

    values_changed = Signal(dict)  # Emits dict with control values

    def __init__(self, title: str, description: str, current_values: dict, parent=None):
        """
        Initialize the layout control dialog.

        Args:
            title: Dialog window title
            description: Description text shown at top
            current_values: Dict with initial values
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(False)  # Allow interaction with main UI
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setMinimumWidth(380)

        # Store current values
        self.current_values = current_values
        self.description_text = description

        # Setup UI
        self._setup_ui()

        # Load current values
        self._load_values(current_values)

    def _setup_ui(self):
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(15, 15, 15, 15)

        # Title
        title = QLabel(self.windowTitle())
        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Description
        desc = QLabel(self.description_text)
        desc.setWordWrap(True)
        desc.setStyleSheet("color: rgb(100, 100, 100); font-size: 9pt;")
        layout.addWidget(desc)

        # Controls container (to be filled by subclass)
        self.controls_layout = QVBoxLayout()
        self.controls_layout.setSpacing(10)
        layout.addLayout(self.controls_layout)

        # Call subclass to add specific controls
        self._setup_controls()

        # Action buttons row
        button_row = QHBoxLayout()

        # Copy Code button
        self.copy_code_btn = QPushButton("📋 Copy Code")
        self.copy_code_btn.setToolTip("Copy current values as Python code to clipboard")
        self.copy_code_btn.clicked.connect(self._copy_code_to_clipboard)
        button_row.addWidget(self.copy_code_btn)

        button_row.addStretch()

        self.reset_btn = QPushButton("Reset to Original")
        self.reset_btn.setToolTip("Reset to the values when dialog was opened")
        self.reset_btn.clicked.connect(lambda: self._load_values(self.current_values))
        button_row.addWidget(self.reset_btn)

        layout.addLayout(button_row)

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _setup_controls(self):
        """Override this method to add your specific controls to self.controls_layout."""
        pass

    def _load_values(self, values: dict):
        """Override this method to load values into your controls."""
        pass

    def _on_value_changed(self):
        """Called when any control value changes. Emits current values."""
        values = self.get_values()
        self.values_changed.emit(values)

    def get_values(self) -> dict:
        """Override this method to return current control values as dict."""
        return {}

    def _copy_code_to_clipboard(self):
        """Copy current values as Python code to clipboard."""
        from PySide6.QtGui import QGuiApplication

        values = self.get_values()
        code = self._generate_code(values)

        clipboard = QGuiApplication.clipboard()
        clipboard.setText(code)

        # Visual feedback
        original_text = self.copy_code_btn.text()
        self.copy_code_btn.setText("✓ Copied!")
        self.copy_code_btn.setStyleSheet("background: #34C759; color: white; border: none; border-radius: 8px; font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;")

        # Reset after 1 second
        def reset_button():
            self.copy_code_btn.setText(original_text)
            self.copy_code_btn.setStyleSheet("")
        QTimer.singleShot(1000, reset_button)

    def _generate_code(self, values: dict) -> str:
        """Generate Python code string from values. Override for custom code generation."""
        lines = ["# Generated values"]
        for key, value in values.items():
            if isinstance(value, str):
                lines.append(f"{key} = '{value}'")
            else:
                lines.append(f"{key} = {value}")
        return "\n".join(lines)

    def accept(self):
        """Override accept to emit final values."""
        values = self.get_values()
        self.values_changed.emit(values)
        super().accept()


class MarginControlDialog(LayoutControlDialog):
    """Example: Margin adjustment dialog using the nimble base."""

    # Alias signal name for backwards compatibility
    margins_changed = LayoutControlDialog.values_changed

    def __init__(self, current_margins: dict, parent=None):
        super().__init__(
            title="Adjust Graph Margins",
            description=(
                "Adjust the margins of the white background rectangle relative to the graph area.\n"
                "Negative values extend beyond the graph area.\n"
                "Changes apply in real-time. Click OK to save or Cancel to revert."
            ),
            current_values=current_margins,
            parent=parent
        )

    def _setup_controls(self):
        """Setup margin-specific controls."""
        # Margin controls group
        margin_group = QGroupBox("Background Rectangle Margins")
        margin_layout = QGridLayout(margin_group)
        margin_layout.setSpacing(10)

        # Left margin
        margin_layout.addWidget(QLabel("Left:"), 0, 0)
        self.left_spin = QSpinBox()
        self.left_spin.setRange(-100, 100)
        self.left_spin.setSuffix(" px")
        self.left_spin.setToolTip("Negative values extend left of the graph area")
        self.left_spin.valueChanged.connect(self._on_value_changed)
        margin_layout.addWidget(self.left_spin, 0, 1)

        # Top margin
        margin_layout.addWidget(QLabel("Top:"), 1, 0)
        self.top_spin = QSpinBox()
        self.top_spin.setRange(-100, 100)
        self.top_spin.setSuffix(" px")
        self.top_spin.setToolTip("Negative values extend above the graph area")
        self.top_spin.valueChanged.connect(self._on_value_changed)
        margin_layout.addWidget(self.top_spin, 1, 1)

        # Right margin
        margin_layout.addWidget(QLabel("Right:"), 2, 0)
        self.right_spin = QSpinBox()
        self.right_spin.setRange(-100, 100)
        self.right_spin.setSuffix(" px")
        self.right_spin.setToolTip("Negative values extend right of the graph area")
        self.right_spin.valueChanged.connect(self._on_value_changed)
        margin_layout.addWidget(self.right_spin, 2, 1)

        # Bottom margin
        margin_layout.addWidget(QLabel("Bottom:"), 3, 0)
        self.bottom_spin = QSpinBox()
        self.bottom_spin.setRange(-100, 100)
        self.bottom_spin.setSuffix(" px")
        self.bottom_spin.setToolTip("Negative values extend below the graph area")
        self.bottom_spin.valueChanged.connect(self._on_value_changed)
        margin_layout.addWidget(self.bottom_spin, 3, 1)

        self.controls_layout.addWidget(margin_group)

        # Border radius group
        border_group = QGroupBox("Border Styling")
        border_layout = QGridLayout(border_group)
        border_layout.setSpacing(10)

        border_layout.addWidget(QLabel("Corner Radius:"), 0, 0)
        self.radius_spin = QSpinBox()
        self.radius_spin.setRange(0, 50)
        self.radius_spin.setSuffix(" px")
        self.radius_spin.setToolTip("Rounded corner radius")
        self.radius_spin.valueChanged.connect(self._on_value_changed)
        border_layout.addWidget(self.radius_spin, 0, 1)

        self.controls_layout.addWidget(border_group)

    def _load_values(self, values: dict):
        """Load margin values into spinboxes."""
        self.left_spin.setValue(values.get('left', 0))
        self.top_spin.setValue(values.get('top', 0))
        self.right_spin.setValue(values.get('right', 0))
        self.bottom_spin.setValue(values.get('bottom', 0))
        self.radius_spin.setValue(values.get('radius', 6))

    def get_values(self) -> dict:
        """Get the current margin values."""
        return {
            'left': self.left_spin.value(),
            'top': self.top_spin.value(),
            'right': self.right_spin.value(),
            'bottom': self.bottom_spin.value(),
            'radius': self.radius_spin.value()
        }

    def _generate_code(self, values: dict) -> str:
        """Generate Python code for margin settings."""
        code = [
            "# Background Rectangle Margin Settings",
            f"self.bg_rect_margin_left = {values['left']}",
            f"self.bg_rect_margin_top = {values['top']}",
            f"self.bg_rect_margin_right = {values['right']}",
            f"self.bg_rect_margin_bottom = {values['bottom']}",
            f"self.bg_rect_radius = {values['radius']}",
            "",
            "# Update rectangle styling",
            "if hasattr(self, 'bg_rect_widget'):",
            "    self.bg_rect_widget.setStyleSheet(",
            "        \"background-color: rgb(255, 255, 255);\"",
            "        \"border: 1px solid rgb(100, 100, 100);\"",
            "        \"border-radius: {self.bg_rect_radius}px;\"",
            "    )",
        ]
        return "\n".join(code)


class PositionControlDialog(LayoutControlDialog):
    """Example: Position and size adjustment dialog."""

    def __init__(self, current_position: dict, parent=None):
        super().__init__(
            title="Adjust Element Position",
            description=(
                "Adjust the position and size of the UI element.\n"
                "Changes apply in real-time. Click OK to save or Cancel to revert."
            ),
            current_values=current_position,
            parent=parent
        )

    def _setup_controls(self):
        """Setup position-specific controls."""
        # Position controls
        pos_group = QGroupBox("Position")
        pos_layout = QGridLayout(pos_group)
        pos_layout.setSpacing(10)

        pos_layout.addWidget(QLabel("X Position:"), 0, 0)
        self.x_spin = QSpinBox()
        self.x_spin.setRange(0, 2000)
        self.x_spin.setSuffix(" px")
        self.x_spin.valueChanged.connect(self._on_value_changed)
        pos_layout.addWidget(self.x_spin, 0, 1)

        pos_layout.addWidget(QLabel("Y Position:"), 1, 0)
        self.y_spin = QSpinBox()
        self.y_spin.setRange(0, 2000)
        self.y_spin.setSuffix(" px")
        self.y_spin.valueChanged.connect(self._on_value_changed)
        pos_layout.addWidget(self.y_spin, 1, 1)

        self.controls_layout.addWidget(pos_group)

        # Size controls
        size_group = QGroupBox("Size")
        size_layout = QGridLayout(size_group)
        size_layout.setSpacing(10)

        size_layout.addWidget(QLabel("Width:"), 0, 0)
        self.width_spin = QSpinBox()
        self.width_spin.setRange(50, 1000)
        self.width_spin.setSuffix(" px")
        self.width_spin.valueChanged.connect(self._on_value_changed)
        size_layout.addWidget(self.width_spin, 0, 1)

        size_layout.addWidget(QLabel("Height:"), 1, 0)
        self.height_spin = QSpinBox()
        self.height_spin.setRange(50, 1000)
        self.height_spin.setSuffix(" px")
        self.height_spin.valueChanged.connect(self._on_value_changed)
        size_layout.addWidget(self.height_spin, 1, 1)

        self.controls_layout.addWidget(size_group)

        # Visibility options
        vis_group = QGroupBox("Visibility")
        vis_layout = QVBoxLayout(vis_group)

        self.visible_check = QCheckBox("Visible")
        self.visible_check.stateChanged.connect(self._on_value_changed)
        vis_layout.addWidget(self.visible_check)

        self.controls_layout.addWidget(vis_group)

    def _load_values(self, values: dict):
        """Load position values into controls."""
        self.x_spin.setValue(values.get('x', 0))
        self.y_spin.setValue(values.get('y', 0))
        self.width_spin.setValue(values.get('width', 100))
        self.height_spin.setValue(values.get('height', 100))
        self.visible_check.setChecked(values.get('visible', True))

    def get_values(self) -> dict:
        """Get the current position values."""
        return {
            'x': self.x_spin.value(),
            'y': self.y_spin.value(),
            'width': self.width_spin.value(),
            'height': self.height_spin.value(),
            'visible': self.visible_check.isChecked()
        }
