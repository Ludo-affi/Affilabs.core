"""Dialog for adjusting background rectangle position and dimensions."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QPushButton,
    QGroupBox,
)


class BgRectDialog(QDialog):
    """Dialog for adjusting background rectangle margins with live preview."""

    def __init__(self, parent=None, data_window=None):
        super().__init__(parent)
        self.data_window = data_window
        self.setWindowTitle("Adjust Background Rectangle")
        self.setModal(False)  # Allow interaction with main window

        # Initial values from the data window - now using margins
        if data_window and hasattr(data_window, 'bg_rect_margin_left'):
            self.margin_left = data_window.bg_rect_margin_left
            self.margin_top = data_window.bg_rect_margin_top
            self.margin_right = data_window.bg_rect_margin_right
            self.margin_bottom = data_window.bg_rect_margin_bottom
            self.radius = data_window.bg_rect_radius
        else:
            self.margin_left = 20
            self.margin_top = 20
            self.margin_right = 20
            self.margin_bottom = 20
            self.radius = 10

        self._setup_ui()

    def _setup_ui(self):
        """Build the dialog UI."""
        layout = QVBoxLayout(self)

        # Margins group
        margin_group = QGroupBox("Margins (pixels from edges)")
        margin_layout = QVBoxLayout()

        # Left margin
        left_row = QHBoxLayout()
        left_row.addWidget(QLabel("Left:"))
        self.margin_left_spin = QSpinBox()
        self.margin_left_spin.setRange(-1000, 1000)
        self.margin_left_spin.setValue(self.margin_left)
        self.margin_left_spin.setSuffix(" px")
        self.margin_left_spin.valueChanged.connect(self._on_param_changed)
        left_row.addWidget(self.margin_left_spin)
        left_row.addStretch()
        margin_layout.addLayout(left_row)

        # Top margin
        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Top:"))
        self.margin_top_spin = QSpinBox()
        self.margin_top_spin.setRange(-1000, 1000)
        self.margin_top_spin.setValue(self.margin_top)
        self.margin_top_spin.setSuffix(" px")
        self.margin_top_spin.valueChanged.connect(self._on_param_changed)
        top_row.addWidget(self.margin_top_spin)
        top_row.addStretch()
        margin_layout.addLayout(top_row)

        # Right margin
        right_row = QHBoxLayout()
        right_row.addWidget(QLabel("Right:"))
        self.margin_right_spin = QSpinBox()
        self.margin_right_spin.setRange(-1000, 1000)
        self.margin_right_spin.setValue(self.margin_right)
        self.margin_right_spin.setSuffix(" px")
        self.margin_right_spin.valueChanged.connect(self._on_param_changed)
        right_row.addWidget(self.margin_right_spin)
        right_row.addStretch()
        margin_layout.addLayout(right_row)

        # Bottom margin
        bottom_row = QHBoxLayout()
        bottom_row.addWidget(QLabel("Bottom:"))
        self.margin_bottom_spin = QSpinBox()
        self.margin_bottom_spin.setRange(-1000, 1000)
        self.margin_bottom_spin.setValue(self.margin_bottom)
        self.margin_bottom_spin.setSuffix(" px")
        self.margin_bottom_spin.valueChanged.connect(self._on_param_changed)
        bottom_row.addWidget(self.margin_bottom_spin)
        bottom_row.addStretch()
        margin_layout.addLayout(bottom_row)

        margin_group.setLayout(margin_layout)
        layout.addWidget(margin_group)

        # Corner radius group
        radius_group = QGroupBox("Corner Radius")
        radius_layout = QHBoxLayout()
        radius_layout.addWidget(QLabel("Radius:"))
        self.radius_spin = QSpinBox()
        self.radius_spin.setRange(0, 50)
        self.radius_spin.setValue(self.radius)
        self.radius_spin.setSuffix(" px")
        self.radius_spin.valueChanged.connect(self._on_param_changed)
        radius_layout.addWidget(self.radius_spin)
        radius_layout.addStretch()
        radius_group.setLayout(radius_layout)
        layout.addWidget(radius_group)

        # Buttons
        btn_layout = QHBoxLayout()

        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self._reset_defaults)
        btn_layout.addWidget(reset_btn)

        btn_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _on_param_changed(self):
        """Update widget when any parameter changes."""
        if self.data_window and hasattr(self.data_window, 'bg_rect_widget'):
            margin_left = self.margin_left_spin.value()
            margin_top = self.margin_top_spin.value()
            margin_right = self.margin_right_spin.value()
            margin_bottom = self.margin_bottom_spin.value()
            radius = self.radius_spin.value()
            
            # Update stored parameters
            self.data_window.bg_rect_margin_left = margin_left
            self.data_window.bg_rect_margin_top = margin_top
            self.data_window.bg_rect_margin_right = margin_right
            self.data_window.bg_rect_margin_bottom = margin_bottom
            self.data_window.bg_rect_radius = radius
            
            # Update border radius and styling
            self.data_window.bg_rect_widget.setStyleSheet(
                f"background-color: rgb(255, 255, 255);"
                f"border: 1px solid rgb(100, 100, 100);"
                f"border-radius: {radius}px;"
            )
            
            # Recalculate position and size
            self.data_window._position_bg_rect()

    def _reset_defaults(self):
        """Reset all parameters to default values."""
        self.margin_left_spin.setValue(-8)
        self.margin_top_spin.setValue(-73)
        self.margin_right_spin.setValue(-9)
        self.margin_bottom_spin.setValue(-12)
        self.radius_spin.setValue(6)
