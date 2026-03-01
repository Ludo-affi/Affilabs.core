"""Modern graph components extracted from UI Prototype Rev 1."""

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from affilabs.ui_styles import FontScale as _FS


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
            "}",
        )
        layout.addWidget(channels_label)

        # Channel toggles - consistent colors (Black, Red, Blue, Green)
        channel_colors = [
            ("A", "#1D1D1F"),      # Channel A: Black
            ("B", "#FF3B30"),      # Channel B: Red
            ("C", "#007AFF"),      # Channel C: Blue (FIXED - was incorrectly black)
            ("D", "#34C759"),      # Channel D: Green
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
                "}",
            )
            self.channel_buttons[ch] = ch_btn
            layout.addWidget(ch_btn)

        layout.addStretch()

    def get_channel_button(self, channel):
        """Get a specific channel button."""
        return self.channel_buttons.get(channel)


class GraphContainer(QFrame):
    """Graph container with title, controls, and graph area."""

    # Channel colours matching the live sensorgram header
    _CH_COLORS = {
        "A": "#1D1D1F",
        "B": "#FF3B30",
        "C": "#007AFF",
        "D": "#34C759",
    }

    def __init__(self, title, height=200, show_delta_spr=False, parent=None):
        super().__init__(parent)
        self.graph_title = title
        self.show_delta = show_delta_spr
        self.delta_display = None
        self.channel_toggles: dict[str, QPushButton] = {}  # only populated when show_delta_spr
        self.reference_channel_id: str | None = None        # currently active ref channel letter
        self._setup_ui(height)

    def _setup_ui(self, height):
        """Setup the container UI."""
        self.setMinimumHeight(height)
        self.setStyleSheet(
            "QFrame {"
            "  background: #FFFFFF;"
            "  border: 1px solid rgba(0, 0, 0, 0.09);"
            "  border-radius: 12px;"
            "}",
        )

        # Add shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(12)

        # Title row with controls
        title_row = self._create_title_row()
        layout.addLayout(title_row)

        # Graph area with axes
        graph_area = self._create_graph_area()
        layout.addWidget(graph_area, 1)

    def _create_title_row(self):
        """Create the title row with controls."""
        from affilabs.ui_styles import get_channel_button_style

        title_row = QHBoxLayout()
        title_row.setSpacing(8)

        # ── Channel toggle buttons (Cycle of Interest graph only) ──────────────
        if self.show_delta:
            _BTN_W, _BTN_H = 32, 28
            for ch, color in self._CH_COLORS.items():
                btn = QPushButton(ch)
                btn.setCheckable(True)
                btn.setChecked(True)
                btn.setFixedSize(_BTN_W, _BTN_H)
                btn.setToolTip(f"Toggle Channel {ch}\nCtrl+click to set/clear as reference channel")
                btn.setProperty("channel_color", color)
                btn.setProperty("channel_letter", ch.lower())
                btn.setStyleSheet(get_channel_button_style(color))
                btn.installEventFilter(self)
                self.channel_toggles[ch] = btn
                title_row.addWidget(btn)
            title_row.addSpacing(8)

        title_row.addStretch()

        # Title label — shown after buttons so it sits right-of-centre
        title_label = QLabel(self.graph_title)
        title_label.setStyleSheet(
            "QLabel {"
            f"  font-size: {_FS.px(18)}px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}",
        )
        title_row.addWidget(title_label)

        title_row.addStretch()

        # Delta SPR signal display (only for Cycle of Interest graph)
        if self.show_delta:
            self.delta_display = QLabel(
                "Δ SPR: Ch A: 0.0 nm  |  Ch B: 0.0 nm  |  Ch C: 0.0 nm  |  Ch D: 0.0 nm",
            )
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
                "}",
            )
            title_row.addWidget(self.delta_display)

        # Zoom/Reset controls
        control_buttons = [
            ("↻", "Reset View (Double-click)"),
            ("+", "Zoom In (Scroll or drag box)"),
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
                "}",
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
            "}",
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
            "}",
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

        x_axis_text = (
            "Time (seconds) - Cycle View" if self.show_delta else "Time (seconds)"
        )
        x_axis_label = QLabel(x_axis_text)
        x_axis_label.setStyleSheet(
            "QLabel {"
            "  font-size: 11px;"
            "  color: #86868B;"
            "  background: transparent;"
            "  font-weight: 500;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}",
        )
        x_axis_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        x_axis_layout.addWidget(x_axis_label)

        graph_layout.addWidget(x_axis_container)

        return graph_area

    # ── Channel toggle / reference helpers ────────────────────────────────────

    def eventFilter(self, obj, event):
        """Intercept Ctrl+click on channel buttons to toggle reference channel."""
        if (event.type() == QEvent.Type.MouseButtonPress
                and event.button() == Qt.MouseButton.LeftButton
                and event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            ch_letter = obj.property("channel_letter")
            if ch_letter:
                self._on_channel_ref_ctrl_click(ch_letter)
                return True
        return super().eventFilter(obj, event)

    def _on_channel_ref_ctrl_click(self, ch_letter: str) -> None:
        """Set or clear reference channel on Ctrl+click."""
        if self.reference_channel_id == ch_letter:
            self.reference_channel_id = None
        else:
            self.reference_channel_id = ch_letter
        self._update_channel_btn_ref_styles()
        # Notify the DataWindow via callback if wired
        cb = getattr(self, '_on_ref_channel_changed', None)
        if callable(cb):
            cb(self.reference_channel_id)

    def _update_channel_btn_ref_styles(self) -> None:
        """Apply dotted border to the reference button; solid to all others."""
        from affilabs.ui_styles import get_channel_button_style, get_channel_button_ref_style
        for ch, btn in self.channel_toggles.items():
            color = btn.property("channel_color") or self._CH_COLORS.get(ch, "#1D1D1F")
            if self.reference_channel_id and ch.lower() == self.reference_channel_id:
                btn.setStyleSheet(get_channel_button_ref_style(color))
            else:
                btn.setStyleSheet(get_channel_button_style(color))

    def set_reference_channel(self, ch_letter: str | None) -> None:
        """Programmatically set reference channel (e.g. from DataWindow.set_reference)."""
        self.reference_channel_id = ch_letter
        self._update_channel_btn_ref_styles()

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
                f"Ch C: {ch_c:.1f} nm  |  Ch D: {ch_d:.1f} nm",
            )
