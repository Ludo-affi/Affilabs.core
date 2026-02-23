"""Interactive SPR Legend Widget - Horizontal, draggable, with white background.

Layout (horizontal pill):
  ⠿  Δ SPR (nm)  │  A ● +0.0  │  B ● +0.0  │  C ● +0.0  │  D ● +0.0

- ⠿ drag handle (SizeAllCursor) — drag anywhere on the handle to reposition
- Title label acts as secondary drag target
- Each channel cell is clickable (selects that channel for timing adjustment)
- IQ dot color + shape (colorblind mode) per channel
- White background, 1px border, drop-shadow
- Value font color matches ACTIVE_GRAPH_COLORS (standard or colorblind palette)
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QFrame,
    QGraphicsDropShadowEffect,
)
from PySide6.QtGui import QFont, QColor, QPainter, QPainterPath

from affilabs.settings import settings


# IQ shape symbols — shape encodes quality in colorblind mode
_IQ_SHAPES = {
    "excellent":    "●",
    "good":         "●",
    "questionable": "▲",
    "poor":         "■",
    "critical":     "✕",
    None:           "●",
}

_FONT_FAMILY = "-apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif"
_MONO = "'SF Mono', 'Cascadia Code', 'Consolas', monospace"


def _color_to_css(color) -> str:
    """Convert settings color value (tuple, "k", or hex string) to CSS color string."""
    if isinstance(color, tuple):
        return f"rgb({color[0]}, {color[1]}, {color[2]})"
    if color == "k":
        return "#000000"
    return str(color)  # already a hex string


class _DragHandle(QLabel):
    """Six-dot drag handle — gives users a clear affordance to grab and move the legend."""

    def __init__(self, parent_legend):
        super().__init__("⠿", parent_legend)
        self._legend = parent_legend
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.setStyleSheet(
            f"color: #C7C7CC; font-size: 16px; font-family: {_FONT_FAMILY};"
            " background: transparent; border: none; padding: 0 4px;"
        )
        self.setToolTip("Drag to reposition")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._legend._drag_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        self._legend._do_drag(event)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._legend._drag_pos = None
        super().mouseReleaseEvent(event)


class InteractiveSPRLegend(QWidget):
    """Horizontal interactive legend — drag handle + title + 4 channel cells."""

    channel_timing_selected = Signal(str)   # channel letter lower — on click
    channel_visibility_changed = Signal(str, bool)  # kept for backward compat

    def __init__(self, parent=None, title="Δ SPR (nm)"):
        super().__init__(parent)
        self.title_text = title
        self.selected_channel = 'a'
        self.channel_values = {'a': 0.0, 'b': 0.0, 'c': 0.0, 'd': 0.0}
        self.iq_colors = {'A': '#C7C7CC', 'B': '#C7C7CC', 'C': '#C7C7CC', 'D': '#C7C7CC'}
        self.iq_levels = {'A': None, 'B': None, 'C': None, 'D': None}
        self._colorblind_mode = False
        self.channel_labels = {}
        self._drag_pos = None      # QPoint set by drag handle press
        self._user_moved = False   # suppresses auto-repositioning after user drag

        self.setObjectName("SPRLegend")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self._init_ui()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(self.rect().adjusted(0, 0, -1, -1), 8, 8)
        painter.fillPath(path, QColor(255, 255, 255, 235))
        painter.setPen(QColor(0, 0, 0, 38))
        painter.drawPath(path)

    # ── Construction ──────────────────────────────────────────────────────────

    def _init_ui(self):
        self.setStyleSheet(
            "#SPRLegend QLabel, #SPRLegend QWidget {"
            "  background: transparent;"
            "  border: none;"
            "}"
        )

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(10)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 28))
        self.setGraphicsEffect(shadow)

        # Main horizontal row
        row = QHBoxLayout(self)
        row.setContentsMargins(6, 5, 8, 5)
        row.setSpacing(0)

        # ── Drag handle ──────────────────────────────────────────────────────
        self._handle = _DragHandle(self)
        row.addWidget(self._handle)

        # ── Title ────────────────────────────────────────────────────────────
        self._title_label = QLabel(self.title_text)
        self._title_label.setCursor(Qt.CursorShape.SizeAllCursor)
        title_font = QFont()
        title_font.setPointSize(9)
        title_font.setBold(True)
        self._title_label.setFont(title_font)
        self._title_label.setStyleSheet(
            f"color: rgba(30,30,30,200); font-family: {_FONT_FAMILY};"
            " background: transparent; padding: 0 8px 0 2px;"
        )
        # Title also participates in drag
        self._title_label.mousePressEvent = self._title_press
        self._title_label.mouseMoveEvent = self._title_move
        self._title_label.mouseReleaseEvent = self._title_release
        row.addWidget(self._title_label)

        # ── Vertical separator ────────────────────────────────────────────────
        row.addWidget(self._make_sep())

        # ── Channel cells ─────────────────────────────────────────────────────
        for i, ch in enumerate(['a', 'b', 'c', 'd']):
            cell = self._create_channel_cell(ch)
            row.addWidget(cell)
            if i < 3:
                row.addWidget(self._make_sep())

        # Default selection highlight
        self._update_channel_appearance('a', True)
        for ch in ['b', 'c', 'd']:
            self._update_channel_appearance(ch, False)

        # Size constraints — width grows naturally with content
        self.setMinimumHeight(32)
        self.setMaximumHeight(44)
        # Don't constrain width — adjustSize() in graphs.py handles it
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def _make_sep(self) -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color: rgba(0,0,0,0.10); background: transparent;")
        sep.setFixedWidth(1)
        return sep

    def _create_channel_cell(self, ch: str) -> QWidget:
        """Single horizontal channel cell: [ch-letter] [iq-dot] [value]."""
        color_str = _color_to_css(settings.ACTIVE_GRAPH_COLORS[ch])

        cell = QWidget()
        cell.setCursor(Qt.CursorShape.PointingHandCursor)
        cell.setProperty("channel", ch)

        layout = QHBoxLayout(cell)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(4)

        # Channel letter
        ch_lbl = QLabel(ch.upper())
        ch_lbl.setStyleSheet(
            f"color: {color_str}; font-weight: 700; font-size: 11px;"
            f" font-family: {_FONT_FAMILY}; background: transparent;"
        )
        layout.addWidget(ch_lbl)

        # IQ dot
        iq_dot = QLabel("●")
        iq_dot.setStyleSheet(
            f"color: {self.iq_colors[ch.upper()]}; font-size: 12px; background: transparent;"
        )
        layout.addWidget(iq_dot)

        # Value
        value_lbl = QLabel("0.0")
        value_lbl.setStyleSheet(
            f"color: {color_str}; font-weight: 600; font-size: 11px;"
            f" font-family: {_MONO}; background: transparent;"
        )
        value_lbl.setMinimumWidth(38)
        layout.addWidget(value_lbl)

        self.channel_labels[ch] = {
            'widget': cell,
            'ch_lbl': ch_lbl,
            'value': value_lbl,
            'iq_dot': iq_dot,
            'iq_color_base': self.iq_colors[ch.upper()],
            'color_str': color_str,
        }

        cell.mousePressEvent = lambda e, c=ch: self._on_channel_clicked(c)
        cell.setStyleSheet("background: transparent; border: none;")
        return cell

    # ── Drag logic ────────────────────────────────────────────────────────────

    def _do_drag(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.position().toPoint() - self._drag_pos
            new_pos = self.pos() + delta
            if self.parent():
                pw, ph = self.parent().width(), self.parent().height()
                new_pos.setX(max(0, min(new_pos.x(), pw - self.width())))
                new_pos.setY(max(0, min(new_pos.y(), ph - self.height())))
            self.move(new_pos)
            self._user_moved = True

    # Title-as-drag-target (lambda replacements for the title label)
    def _title_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.position().toPoint()

    def _title_move(self, event):
        self._do_drag(event)

    def _title_release(self, event):
        self._drag_pos = None

    # ── Channel interaction ───────────────────────────────────────────────────

    def _on_channel_clicked(self, channel: str):
        self.selected_channel = channel
        for ch in self.channel_labels:
            self._update_channel_appearance(ch, ch == channel)
        self.channel_timing_selected.emit(channel)

    def _update_channel_appearance(self, channel: str, is_selected: bool):
        if channel not in self.channel_labels:
            return
        cell = self.channel_labels[channel]['widget']
        if is_selected:
            cell.setStyleSheet("background: rgba(0,122,255,0.10); border-radius: 4px;")
        else:
            cell.setStyleSheet("background: transparent; border: none;")

    # ── Public API ────────────────────────────────────────────────────────────

    def update_values(self, delta_values: dict):
        """Update SPR Δ values for all channels.

        Args:
            delta_values: {'a': float, 'b': float, 'c': float, 'd': float}
        """
        for ch, value in delta_values.items():
            if ch in self.channel_labels:
                sign = "+" if value >= 0 else ""
                self.channel_labels[ch]['value'].setText(f"{sign}{value:.1f}")

    def set_iq_state(self, channel: str, hex_color: str, iq_level: str | None = None):
        """Update IQ dot color and shape for a channel."""
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
        iq_dot.setStyleSheet(f"color: {hex_color}; font-size: 12px; background: transparent;")

    def set_iq_color(self, channel: str, hex_color: str):
        """Backward-compat wrapper — delegates to set_iq_state."""
        ch = channel.lower()
        iq_level = self.iq_levels.get(channel.upper())
        self.set_iq_state(ch, hex_color, iq_level)

    def set_colorblind_mode(self, enabled: bool):
        """Switch IQ dot shape encoding and refresh value + channel label colors."""
        self._colorblind_mode = enabled
        # Refresh IQ dots (shape encoding)
        for ch_lower in ['a', 'b', 'c', 'd']:
            ch_upper = ch_lower.upper()
            color = self.channel_labels[ch_lower]['iq_color_base']
            iq_level = self.iq_levels.get(ch_upper)
            shape = _IQ_SHAPES.get(iq_level, "●") if enabled else "●"
            iq_dot = self.channel_labels[ch_lower]['iq_dot']
            iq_dot.setText(shape)
            iq_dot.setStyleSheet(f"color: {color}; font-size: 12px; background: transparent;")
        # Also update value label colors to match new palette
        self.update_colors()

    def update_colors(self):
        """Refresh channel letter + value label colors from ACTIVE_GRAPH_COLORS.

        Called after colorblind mode toggle — reads the already-updated palette.
        """
        for ch in ['a', 'b', 'c', 'd']:
            if ch not in self.channel_labels:
                continue
            color_str = _color_to_css(settings.ACTIVE_GRAPH_COLORS[ch])
            info = self.channel_labels[ch]
            info['color_str'] = color_str
            info['ch_lbl'].setStyleSheet(
                f"color: {color_str}; font-weight: 700; font-size: 11px;"
                f" font-family: {_FONT_FAMILY}; background: transparent;"
            )
            info['value'].setStyleSheet(
                f"color: {color_str}; font-weight: 600; font-size: 11px;"
                f" font-family: {_MONO}; background: transparent;"
            )

    def set_title(self, title: str):
        self.title_text = title
        self._title_label.setText(title)

    def reset(self):
        """Reset legend to default state."""
        self.selected_channel = 'a'
        for ch in self.channel_labels:
            self._update_channel_appearance(ch, ch == 'a')
            self.channel_labels[ch]['value'].setText("0.0")
            iq_dot = self.channel_labels[ch]['iq_dot']
            iq_dot.setText("●")
            iq_dot.setStyleSheet("color: #C7C7CC; font-size: 12px; background: transparent;")
            self.channel_labels[ch]['iq_color_base'] = '#C7C7CC'
        self.iq_colors = {'A': '#C7C7CC', 'B': '#C7C7CC', 'C': '#C7C7CC', 'D': '#C7C7CC'}
        self.iq_levels = {'A': None, 'B': None, 'C': None, 'D': None}
