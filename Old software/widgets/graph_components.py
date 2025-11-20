"""Modern graph components extracted from UI Prototype Rev 1."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton
)
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect


class GraphHeader(QWidget):
    """Graph header with channel toggle controls."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.channel_buttons = {}
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the header UI."""
        self.setFixedHeight(48)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Channel selection label
        channels_label = QLabel("Channels:")
        channels_label.setStyleSheet(
            "QLabel {"
            "  font-size: 13px;"
            "  color: #86868B;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "  font-weight: 500;"
            "}"
        )
        layout.addWidget(channels_label)
        
        # Channel toggles - consistent colors (Black, Red, Blue, Green)
        channel_colors = [
            ("A", "#1D1D1F"),
            ("B", "#FF3B30"),
            ("C", "#007AFF"),
            ("D", "#34C759")
        ]
        
        for ch, color in channel_colors:
            ch_btn = QPushButton(f"Ch {ch}")
            ch_btn.setCheckable(True)
            ch_btn.setChecked(True)
            ch_btn.setFixedSize(56, 32)
            ch_btn.setStyleSheet(
                f"QPushButton {{"
                f"  background: {color};"
                "  color: white;"
                "  border: none;"
                "  border-radius: 6px;"
                "  font-size: 12px;"
                "  font-weight: 600;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:!checked {"
                "  background: rgba(0, 0, 0, 0.06);"
                "  color: #86868B;"
                "}"
                "QPushButton:hover:!checked {"
                "  background: rgba(0, 0, 0, 0.1);"
                "}"
            )
            self.channel_buttons[ch] = ch_btn
            layout.addWidget(ch_btn)
        
        layout.addStretch()
    
    def get_channel_button(self, channel):
        """Get a specific channel button."""
        return self.channel_buttons.get(channel)


class GraphContainer(QFrame):
    """Graph container with title, controls, and graph area."""
    
    def __init__(self, title, height=200, show_delta_spr=False, parent=None):
        super().__init__(parent)
        self.graph_title = title
        self.show_delta = show_delta_spr
        self.delta_display = None
        self._setup_ui(height)
    
    def _setup_ui(self, height):
        """Setup the container UI."""
        self.setMinimumHeight(height)
        self.setStyleSheet(
            "QFrame {"
            "  background: #FFFFFF;"
            "  border: none;"
            "  border-radius: 12px;"
            "}"
        )
        
        # Add shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Title row with controls
        title_row = self._create_title_row()
        layout.addLayout(title_row)
        
        # Graph area with axes
        graph_area = self._create_graph_area()
        layout.addWidget(graph_area, 1)
    
    def _create_title_row(self):
        """Create the title row with controls."""
        title_row = QHBoxLayout()
        title_row.setSpacing(12)
        
        # Title label
        title_label = QLabel(self.graph_title)
        title_label.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        title_row.addWidget(title_label)
        
        title_row.addStretch()
        
        # Delta SPR signal display (only for Cycle of Interest graph)
        if self.show_delta:
            self.delta_display = QLabel("Δ SPR: Ch A: 0.0 nm  |  Ch B: 0.0 nm  |  Ch C: 0.0 nm  |  Ch D: 0.0 nm")
            self.delta_display.setStyleSheet(
                "QLabel {"
                "  background: rgba(0, 0, 0, 0.04);"
                "  border: none;"
                "  border-radius: 6px;"
                "  padding: 6px 12px;"
                "  font-size: 11px;"
                "  color: #1D1D1F;"
                "  font-family: -apple-system, 'SF Mono', 'Menlo', monospace;"
                "  font-weight: 500;"
                "}"
            )
            title_row.addWidget(self.delta_display)
        
        # Zoom/Reset controls
        control_buttons = [
            ("↻", "Reset View (Double-click)"),
            ("+", "Zoom In (Scroll or drag box)")
        ]
        
        for icon, tooltip in control_buttons:
            control_btn = QPushButton(icon)
            control_btn.setFixedSize(32, 24)
            control_btn.setStyleSheet(
                "QPushButton {"
                "  background: rgba(0, 0, 0, 0.06);"
                "  color: #1D1D1F;"
                "  border: none;"
                "  border-radius: 4px;"
                "  font-size: 14px;"
                "  font-weight: 500;"
                "  font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:hover {"
                "  background: rgba(0, 0, 0, 0.1);"
                "}"
                "QPushButton:pressed {"
                "  background: rgba(0, 0, 0, 0.14);"
                "}"
            )
            control_btn.setToolTip(tooltip)
            title_row.addWidget(control_btn)
        
        return title_row
    
    def _create_graph_area(self):
        """Create the graph area with axis labels."""
        graph_area = QFrame()
        graph_area.setStyleSheet(
            "QFrame {"
            "  background: #FFFFFF;"
            "  border: 1px solid rgba(0, 0, 0, 0.08);"
            "  border-radius: 8px;"
            "}"
        )
        
        graph_layout = QVBoxLayout(graph_area)
        graph_layout.setContentsMargins(8, 8, 8, 8)
        graph_layout.setSpacing(0)
        
        # Canvas container with Y-axis
        canvas_container = QWidget()
        canvas_layout = QHBoxLayout(canvas_container)
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        canvas_layout.setSpacing(4)
        
        # Y-axis label (vertical)
        y_axis_label = QLabel("Δ Wavelength (nm)")
        y_axis_label.setStyleSheet(
            "QLabel {"
            "  font-size: 11px;"
            "  color: #86868B;"
            "  background: transparent;"
            "  font-weight: 500;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        y_axis_label.setMaximumWidth(20)
        y_axis_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        canvas_layout.addWidget(y_axis_label)
        
        # Main graph placeholder (will be replaced with PyQtGraph widget)
        self.graph_widget = QFrame()
        self.graph_widget.setStyleSheet("background: #FAFAFA;")
        canvas_layout.addWidget(self.graph_widget, 1)
        
        graph_layout.addWidget(canvas_container, 1)
        
        # X-axis label (horizontal)
        x_axis_container = QWidget()
        x_axis_layout = QHBoxLayout(x_axis_container)
        x_axis_layout.setContentsMargins(24, 4, 0, 0)
        x_axis_layout.setSpacing(0)
        
        x_axis_text = "Time (seconds) - Cycle View" if self.show_delta else "Time (seconds)"
        x_axis_label = QLabel(x_axis_text)
        x_axis_label.setStyleSheet(
            "QLabel {"
            "  font-size: 11px;"
            "  color: #86868B;"
            "  background: transparent;"
            "  font-weight: 500;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        x_axis_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        x_axis_layout.addWidget(x_axis_label)
        
        graph_layout.addWidget(x_axis_container)
        
        return graph_area
    
    def set_graph_widget(self, widget):
        """Replace the placeholder with actual graph widget."""
        # Remove placeholder
        layout = self.graph_widget.parent().layout()
        layout.removeWidget(self.graph_widget)
        self.graph_widget.deleteLater()
        
        # Add new widget
        self.graph_widget = widget
        layout.insertWidget(1, widget, 1)
    
    def update_delta_spr(self, ch_a, ch_b, ch_c, ch_d):
        """Update delta SPR display values."""
        if self.delta_display:
            self.delta_display.setText(
                f"Δ SPR: Ch A: {ch_a:.1f} nm  |  Ch B: {ch_b:.1f} nm  |  "
                f"Ch C: {ch_c:.1f} nm  |  Ch D: {ch_d:.1f} nm"
            )
