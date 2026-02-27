"""CycleStatusOverlay — live-cycle status embedded inside the Active Cycle graph.

Shown automatically when a cycle starts, hidden when it ends.
Draggable via the ⠿ handle — same UX pattern as InteractiveSPRLegend.

Layout::

    ⠿  Binding  2 / 5   04:34
       Next: Rinse · Exp: 20m 34s left
"""

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)

logger = logging.getLogger(__name__)

_FONT  = "-apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif"
_MONO  = "'SF Mono', 'Cascadia Code', 'Consolas', monospace"
_WARN  = "#FF9500"
_MUTED = "#86868B"
_TEXT  = "#1D1D1F"


class CycleStatusOverlay(QWidget):
    """Compact cycle-progress chip embedded inside the Active Cycle PlotWidget.

    Draggable via the ⠿ handle.  After the user moves it, auto-repositioning
    on each tick is suppressed.

    Call ``update_status(...)`` every second from ``_update_cycle_display``.
    Call ``clear()`` when the cycle ends.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CycleStatusOverlay")
        self.setVisible(False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        self._drag_pos = None      # QPoint relative to widget origin while dragging
        self._user_moved = False   # True once user has repositioned manually
        self._collapsed = False    # minimized state

        self._init_ui()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(self.rect().adjusted(0, 0, -1, -1), 8, 8)
        painter.fillPath(path, QColor(255, 255, 255, 235))
        painter.setPen(QColor(0, 0, 0, 38))
        painter.drawPath(path)

    # ── UI construction ───────────────────────────────────────────────────────

    def _init_ui(self):
        self.setStyleSheet(
            "QWidget#CycleStatusOverlay QLabel {"
            "  background: transparent;"
            "  border: none;"
            "}"
        )

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(10)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 28))
        self.setGraphicsEffect(shadow)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 5, 10, 6)
        root.setSpacing(3)

        # ── Row 1: drag handle + type badge + index + countdown ───────────
        row1 = QHBoxLayout()
        row1.setSpacing(6)
        row1.setContentsMargins(0, 0, 0, 0)

        # Drag handle
        self._handle = QLabel("⠿")
        self._handle.setCursor(Qt.CursorShape.SizeAllCursor)
        self._handle.setStyleSheet(
            f"color: #C7C7CC; font-size: 16px; font-family: {_FONT};"
            " background: transparent; padding: 0 2px 0 0;"
        )
        self._handle.setToolTip("Drag to reposition")
        row1.addWidget(self._handle)

        self._type_label = QLabel("—")
        self._type_label.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {_TEXT}; font-family: {_FONT};"
        )
        row1.addWidget(self._type_label)

        self._index_label = QLabel("")
        self._index_label.setStyleSheet(
            f"font-size: 12px; font-weight: 500; color: {_MUTED}; font-family: {_FONT};"
        )
        row1.addWidget(self._index_label)

        row1.addStretch()

        # ── Minimize / expand toggle ───────────────────────────────────────
        self._toggle_btn = QLabel("▾")
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.setStyleSheet(
            f"color: #86868B; font-size: 11px; font-family: {_FONT};"
            " background: transparent; border: none; padding: 0 2px;"
        )
        self._toggle_btn.setToolTip("Minimize")
        self._toggle_btn.mousePressEvent = lambda e: self._toggle_collapse()
        row1.addWidget(self._toggle_btn)

        root.addLayout(row1)

        # ── Collapsible content: index label is kept, row 2 is hidden ─────
        self._collapse_widgets = []  # widgets hidden when collapsed

        # ── Row 2: next-cycle hint + exp time remaining ───────────────────
        self._row2_widget = QWidget()
        row2 = QHBoxLayout(self._row2_widget)
        row2.setSpacing(6)
        row2.setContentsMargins(22, 0, 0, 0)  # indent past drag handle

        self._next_label = QLabel("")
        self._next_label.setStyleSheet(
            f"font-size: 11px; font-weight: 500; color: {_WARN}; font-family: {_FONT};"
        )
        self._next_label.setVisible(False)
        row2.addWidget(self._next_label)

        # Binding response signal (shown during injection contact window)
        self._binding_label = QLabel("")
        self._binding_label.setStyleSheet(
            f"font-size: 11px; font-weight: 600; color: {_MUTED}; font-family: {_MONO};"
        )
        self._binding_label.setVisible(False)
        row2.addWidget(self._binding_label)

        row2.addStretch()

        # Slope label (right-aligned in row 2)
        self._slope_label = QLabel("")
        self._slope_label.setStyleSheet(
            f"font-size: 10px; font-weight: 500; color: {_MUTED}; font-family: {_MONO};"
        )
        self._slope_label.setVisible(False)
        row2.addWidget(self._slope_label)

        self._collapse_widgets.append(self._row2_widget)
        self._collapse_widgets.append(self._index_label)
        root.addWidget(self._row2_widget)

        self.adjustSize()

    # ── Collapse / expand ─────────────────────────────────────────────────────

    def _toggle_collapse(self):
        """Toggle between expanded (full detail) and collapsed (type only)."""
        self._collapsed = not self._collapsed
        for w in self._collapse_widgets:
            w.setVisible(not self._collapsed)
        self._toggle_btn.setText("▸" if self._collapsed else "▾")
        self._toggle_btn.setToolTip("Expand" if self._collapsed else "Minimize")
        self.adjustSize()

    # ── Drag logic ────────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.position().toPoint() - self._drag_pos
            new_pos = self.pos() + delta
            if self.parent():
                pw, ph = self.parent().width(), self.parent().height()
                new_pos.setX(max(0, min(new_pos.x(), pw - self.width())))
                new_pos.setY(max(0, min(new_pos.y(), ph - self.height())))
            self.move(new_pos)
            self._user_moved = True
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    # ── Public API ────────────────────────────────────────────────────────────

    def update_status(
        self,
        cycle_type: str,
        cycle_num: int,
        total_cycles: int,
        remaining_sec: float,
        next_label: str = "",
        injection_active: bool = False,
        contact_remaining_sec: int | None = None,  # unused — contact timer lives in InjectionActionBar
        contact_channel: str = "",  # unused
    ) -> None:
        """Refresh all displayed fields. Shows the overlay on first call."""
        self._type_label.setText(cycle_type)
        self._index_label.setText(f"{cycle_num} / {total_cycles}")

        if injection_active:
            self._next_label.setText("Contact time → Injection Assistant")
            self._next_label.setStyleSheet(
                f"font-size: 10px; font-weight: 500; color: #007AFF; font-family: {_FONT};"
            )
            self._next_label.setVisible(True)
        elif next_label:
            self._next_label.setText(next_label)
            self._next_label.setStyleSheet(
                f"font-size: 11px; font-weight: 500; color: {_WARN}; font-family: {_FONT};"
            )
            self._next_label.setVisible(True)
        else:
            self._next_label.setVisible(False)

        if not self.isVisible():
            self.setVisible(True)

        # Re-anchor to top-right only if user hasn't dragged it
        if not self._user_moved:
            parent = self.parentWidget()
            if parent is not None:
                self.adjustSize()
                x = max(62, parent.width() - self.width() - 10)
                self.move(x, 10)

        self.raise_()

    def show_complete(self) -> None:
        """Switch overlay to 'Method Complete' state after all cycles finish."""
        _GREEN = "#34C759"
        self._type_label.setText("Method Complete  ✓")
        self._type_label.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {_GREEN}; font-family: {_FONT};"
        )
        self._index_label.setText("")
        self._next_label.setVisible(False)

        if not self.isVisible():
            self.setVisible(True)
        if not self._user_moved:
            parent = self.parentWidget()
            if parent is not None:
                self.adjustSize()
                x = max(62, parent.width() - self.width() - 10)
                self.move(x, 10)
        self.raise_()

    def show_cycle_result(self, label: str, color: str) -> None:
        """Display a brief end-of-cycle result summary in row 2.

        Replaces binding signal labels with a single result string for ~3 s
        (caller is responsible for scheduling clear() or next update_status()).
        """
        self._next_label.setVisible(False)
        self._slope_label.setVisible(False)

        self._binding_label.setText(label)
        self._binding_label.setStyleSheet(
            f"font-size: 11px; font-weight: 700; color: {color}; font-family: {_FONT};"
        )
        self._binding_label.setVisible(True)
        self.adjustSize()

    def clear(self) -> None:
        """Hide the overlay when no cycle is running."""
        self.setVisible(False)
        self._user_moved = False  # reset so next cycle starts anchored top-right
        # Reset collapsed state so next cycle starts expanded
        if self._collapsed:
            self._collapsed = False
            for w in self._collapse_widgets:
                w.setVisible(True)
            self._toggle_btn.setText("▾")
            self._toggle_btn.setToolTip("Minimize")
        # reset type label color so it's correct next run
        self._type_label.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {_TEXT}; font-family: {_FONT};"
        )
        self._binding_label.setVisible(False)
        self._slope_label.setVisible(False)
