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
    """Horizontal interactive legend — drag handle + title + 4 channel cells.

    Minimizable: click the ▾ button to collapse to a compact pill showing only
    the drag handle and title.  Click ▸ to expand.
    """

    channel_timing_selected = Signal(str)   # channel letter lower — on click
    channel_visibility_changed = Signal(str, bool)  # kept for backward compat
    channel_nudge_requested = Signal(str, float)    # (channel_lower, delta_seconds)

    def __init__(self, parent=None, title="Δ SPR (nm)"):
        super().__init__(parent)
        self.title_text = title
        self.selected_channel = 'a'
        self.channel_values = {'a': 0.0, 'b': 0.0, 'c': 0.0, 'd': 0.0}
        self.channel_labels = {}
        self._drag_pos = None      # QPoint set by drag handle press
        self._user_moved = False   # suppresses auto-repositioning after user drag
        self._collapsed = False    # minimized state
        self._user_has_selected = False  # True after first deliberate channel click

        self.setObjectName("SPRLegend")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
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
        title_font.setPointSize(11)
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

        # ── Minimize / expand toggle ──────────────────────────────────────────
        self._toggle_btn = QLabel("▾")
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.setStyleSheet(
            f"color: #86868B; font-size: 13px; font-family: {_FONT_FAMILY};"
            " background: transparent; border: none; padding: 0 4px;"
        )
        self._toggle_btn.setToolTip("Minimize")
        self._toggle_btn.mousePressEvent = lambda e: self._toggle_collapse()
        row.addWidget(self._toggle_btn)

        # ── Collapsible content container ─────────────────────────────────────
        self._content_widgets = []  # widgets to show/hide on collapse

        # ── Vertical separator ────────────────────────────────────────────────
        sep0 = self._make_sep()
        self._content_widgets.append(sep0)
        row.addWidget(sep0)

        # ── Channel cells ─────────────────────────────────────────────────────
        for i, ch in enumerate(['a', 'b', 'c', 'd']):
            cell = self._create_channel_cell(ch)
            self._content_widgets.append(cell)
            row.addWidget(cell)
            if i < 3:
                sep = self._make_sep()
                self._content_widgets.append(sep)
                row.addWidget(sep)

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
        """Single horizontal channel cell: [value]."""
        color_str = _color_to_css(settings.ACTIVE_GRAPH_COLORS[ch])

        cell = QWidget()
        cell.setCursor(Qt.CursorShape.PointingHandCursor)
        cell.setProperty("channel", ch)

        layout = QHBoxLayout(cell)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(4)

        # Value
        value_lbl = QLabel("0.0")
        value_lbl.setStyleSheet(
            f"color: {color_str}; font-weight: 600; font-size: 13px;"
            f" font-family: {_MONO}; background: transparent;"
        )
        value_lbl.setMinimumWidth(38)
        layout.addWidget(value_lbl)

        self.channel_labels[ch] = {
            'widget': cell,
            'value': value_lbl,
            'color_str': color_str,
        }

        cell.mousePressEvent = lambda e, c=ch: self._on_channel_clicked(c)
        value_lbl.mousePressEvent = lambda e, c=ch: self._on_channel_clicked(c)
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

    # ── Collapse / expand ─────────────────────────────────────────────────────

    def _toggle_collapse(self):
        """Toggle between expanded (all channels visible) and collapsed (title only)."""
        self._collapsed = not self._collapsed
        for w in self._content_widgets:
            w.setVisible(not self._collapsed)
        self._toggle_btn.setText("▸" if self._collapsed else "▾")
        self._toggle_btn.setToolTip("Expand" if self._collapsed else "Minimize")
        self.adjustSize()

    # ── Channel interaction ───────────────────────────────────────────────────

    def _on_channel_clicked(self, channel: str):
        self.setFocus()
        self._user_has_selected = True
        self.selected_channel = channel
        for ch in self.channel_labels:
            self._update_channel_appearance(ch, ch == channel)
        self.channel_timing_selected.emit(channel)

    _CHANNELS = ['a', 'b', 'c', 'd']

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            # Shift = coarse (5 s), plain = fine (1 s)
            step = 5.0 if (event.modifiers() & Qt.KeyboardModifier.ShiftModifier) else 1.0
            delta = -step if key == Qt.Key.Key_Left else step
            if self.selected_channel:
                self.channel_nudge_requested.emit(self.selected_channel, delta)
        else:
            super().keyPressEvent(event)

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
                self.channel_labels[ch]['value'].setText(f"{sign}{int(round(value))}")

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
            info['value'].setStyleSheet(
                f"color: {color_str}; font-weight: 600; font-size: 13px;"
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
            self.channel_labels[ch]['value'].setText("0")
