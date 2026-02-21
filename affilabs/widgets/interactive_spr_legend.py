"""Interactive SPR Legend Widget - Clickable channel display with real-time values.

Replaces the static legend with an interactive widget that:
- Shows real-time SPR/wavelength values per channel
- Selects channel for timing adjustment on click
- Displays signal quality indicators (IQ dots) with color + shape encoding
- Color-coded by channel
- Positioned top-left of Active Cycle graph
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtGui import QFont

from affilabs.settings import settings


# IQ shape symbols — used in colorblind mode (shape encodes quality, not just color)
# Also shown in standard mode so meaning is always legible
_IQ_SHAPES = {
    "excellent":    "●",   # filled circle — all good
    "good":         "●",   # filled circle
    "questionable": "▲",   # triangle — caution
    "poor":         "■",   # square — warning
    "critical":     "✕",   # X — error
    None:           "●",   # default / unknown
}


class InteractiveSPRLegend(QWidget):
    """Interactive legend showing channel timing selection, values, and signal quality."""

    channel_timing_selected = Signal(str)  # (channel_letter_lower) — emitted on click

    def __init__(self, parent=None, title="Δ SPR (nm)"):
        super().__init__(parent)
        self.title_text = title
        self.selected_channel = 'a'  # currently highlighted for timing
        self.channel_values = {'a': 0.0, 'b': 0.0, 'c': 0.0, 'd': 0.0}
        self.iq_colors = {'A': '#C7C7CC', 'B': '#C7C7CC', 'C': '#C7C7CC', 'D': '#C7C7CC'}
        self.iq_levels = {'A': None, 'B': None, 'C': None, 'D': None}
        self._colorblind_mode = False
        self.channel_labels = {}
        self._init_ui()

    def _init_ui(self):
        """Initialize the interactive legend UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # Title label
        title_label = QLabel(self.title_text)
        title_font = QFont()
        title_font.setPointSize(10)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: rgba(30, 30, 30, 220); background: transparent;")
        layout.addWidget(title_label)

        # Channel rows (each channel clickable)
        for ch in ['a', 'b', 'c', 'd']:
            row_widget = self._create_channel_row(ch)
            layout.addWidget(row_widget)

        layout.addStretch()
        self.setObjectName("SPRLegend")
        self.setStyleSheet(
            "#SPRLegend {"
            "  background: #FFFFFF;"
            "  border: 1px solid rgba(0,0,0,0.10);"
            "  border-radius: 10px;"
            "}"
            "#SPRLegend QWidget, #SPRLegend QLabel {"
            "  background: transparent;"
            "  border: none;"
            "}"
        )
        from PySide6.QtWidgets import QGraphicsDropShadowEffect
        from PySide6.QtGui import QColor
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(12)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 30))
        self.setGraphicsEffect(shadow)
        self.setMaximumWidth(120)
        self.setMinimumWidth(100)

        # Highlight default selected channel (a)
        self._update_channel_appearance('a', True)
        for ch in ['b', 'c', 'd']:
            self._update_channel_appearance(ch, False)

    def _create_channel_row(self, ch):
        """Create a clickable row for a single channel."""
        row = QWidget()
        row.setCursor(Qt.CursorShape.PointingHandCursor)
        row.setProperty("channel", ch)

        layout = QHBoxLayout(row)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        # Get color from settings
        color = settings.ACTIVE_GRAPH_COLORS[ch]
        if isinstance(color, tuple):
            color_str = f"rgb({color[0]}, {color[1]}, {color[2]})"
        else:
            color_str = color

        # IQ dot — shape changes with IQ level in colorblind mode
        iq_dot = QLabel("●")
        iq_dot.setStyleSheet(f"color: {self.iq_colors[ch.upper()]}; font-size: 14px; background: transparent;")
        layout.addWidget(iq_dot, 0, Qt.AlignmentFlag.AlignCenter)

        # Value only (channel letter removed — display buttons above serve as labels)
        value_label = QLabel("0.0")
        value_label.setStyleSheet(f"color: {color_str}; font-weight: 600; font-size: 12px; background: transparent;")
        value_label.setFixedWidth(45)
        layout.addWidget(value_label)

        # Store references
        self.channel_labels[ch] = {
            'widget': row,
            'value': value_label,
            'iq_dot': iq_dot,
            'iq_color_base': self.iq_colors[ch.upper()]
        }

        # Make clickable
        row.mousePressEvent = lambda e, channel=ch: self._on_channel_clicked(channel)
        row.setStyleSheet("background: transparent; border: none;")
        return row

    def _on_channel_clicked(self, channel):
        """Handle channel row click — selects channel for timing adjustment."""
        self.selected_channel = channel
        for ch in self.channel_labels:
            self._update_channel_appearance(ch, ch == channel)
        self.channel_timing_selected.emit(channel)

    def _update_channel_appearance(self, channel, is_selected):
        """Update row appearance based on selection state."""
        if channel not in self.channel_labels:
            return

        row_info = self.channel_labels[channel]
        row = row_info['widget']
        iq_dot = row_info['iq_dot']

        iq_dot.setStyleSheet(
            f"color: {row_info['iq_color_base']}; font-size: 14px; "
            f"background: transparent; border: none;"
        )
        if is_selected:
            row.setStyleSheet("background: rgba(0, 122, 255, 0.10); border-radius: 4px;")
        else:
            row.setStyleSheet("background: transparent; border: none;")

    def update_values(self, delta_values: dict):
        """Update SPR values for all channels.

        Args:
            delta_values: Dictionary with keys 'a', 'b', 'c', 'd' containing nm values
        """
        for ch, value in delta_values.items():
            if ch in self.channel_labels:
                sign = "+" if value >= 0 else ""
                self.channel_labels[ch]['value'].setText(f"{sign}{value:.1f}")

    def set_iq_state(self, channel: str, hex_color: str, iq_level: str | None = None):
        """Update the IQ dot color and shape for a channel.

        In colorblind mode the shape also changes (● ▲ ■ ✕) so quality is
        legible without relying on color alone.

        Args:
            channel: Channel letter, upper or lower case ('A'/'a')
            hex_color: IQ color string (e.g. '#34C759')
            iq_level: IQ level key ('excellent', 'good', 'questionable', 'poor', 'critical')
        """
        ch = channel.lower()
        if ch not in self.channel_labels:
            return

        ch_upper = ch.upper()
        self.channel_labels[ch]['iq_color_base'] = hex_color
        self.iq_colors[ch_upper] = hex_color
        self.iq_levels[ch_upper] = iq_level

        shape = _IQ_SHAPES.get(iq_level, "●") if self._colorblind_mode else "●"
        iq_dot = self.channel_labels[ch]['iq_dot']
        iq_dot.setText(shape)
        iq_dot.setStyleSheet(f"color: {hex_color}; font-size: 14px; background: transparent;")

    def set_iq_color(self, channel: str, hex_color: str):
        """Thin wrapper kept for backward compatibility — delegates to set_iq_state."""
        ch = channel.lower()
        iq_level = self.iq_levels.get(channel.upper())
        self.set_iq_state(ch, hex_color, iq_level)

    def set_colorblind_mode(self, enabled: bool):
        """Switch between color-only and color+shape IQ encoding.

        Refreshes all IQ dots immediately with current stored IQ levels.
        """
        self._colorblind_mode = enabled
        for ch_lower in ['a', 'b', 'c', 'd']:
            ch_upper = ch_lower.upper()
            color = self.channel_labels[ch_lower]['iq_color_base']
            iq_level = self.iq_levels.get(ch_upper)
            shape = _IQ_SHAPES.get(iq_level, "●") if enabled else "●"
            iq_dot = self.channel_labels[ch_lower]['iq_dot']
            iq_dot.setText(shape)
            iq_dot.setStyleSheet(f"color: {color}; font-size: 14px; background: transparent;")

    def update_colors(self):
        """Refresh channel value label colors from settings (called after colorblind mode toggle)."""
        for ch in ['a', 'b', 'c', 'd']:
            if ch not in self.channel_labels:
                continue
            color = settings.ACTIVE_GRAPH_COLORS[ch]
            if isinstance(color, tuple):
                color_str = f"rgb({color[0]}, {color[1]}, {color[2]})"
            else:
                color_str = color
            value_widget = self.channel_labels[ch].get('value')
            if value_widget:
                value_widget.setStyleSheet(f"color: {color_str}; font-weight: 600; font-size: 12px; background: transparent;")

    def set_title(self, title: str):
        """Update the legend title."""
        self.title_text = title

    def reset(self):
        """Reset legend to default state."""
        self.selected_channel = 'a'
        for ch in self.channel_labels:
            self._update_channel_appearance(ch, ch == 'a')
            self.channel_labels[ch]['value'].setText("0.0")
            # Reset IQ dot to default
            iq_dot = self.channel_labels[ch]['iq_dot']
            iq_dot.setText("●")
            iq_dot.setStyleSheet("color: #C7C7CC; font-size: 14px; background: transparent;")
        self.iq_colors = {'A': '#C7C7CC', 'B': '#C7C7CC', 'C': '#C7C7CC', 'D': '#C7C7CC'}
        self.iq_levels = {'A': None, 'B': None, 'C': None, 'D': None}
        for ch in self.channel_labels:
            self.channel_labels[ch]['iq_color_base'] = '#C7C7CC'
