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
_ACCENT = "#2E30E3"
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

        self._countdown_label = QLabel("00:00")
        self._countdown_label.setStyleSheet(
            f"font-size: 22px; font-weight: 700; color: {_ACCENT}; font-family: {_MONO};"
        )
        row1.addWidget(self._countdown_label)

        root.addLayout(row1)

        # ── Row 2: next-cycle hint + exp time remaining ───────────────────
        row2 = QHBoxLayout()
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

        root.addLayout(row2)

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
    ) -> None:
        """Refresh all displayed fields. Shows the overlay on first call."""
        rem_min = int(remaining_sec // 60)
        rem_sec = int(remaining_sec % 60)

        self._type_label.setText(cycle_type)
        self._index_label.setText(f"{cycle_num} / {total_cycles}")
        self._countdown_label.setText(f"{rem_min:02d}:{rem_sec:02d}")

        color = _WARN if remaining_sec <= 10 else _ACCENT
        self._countdown_label.setStyleSheet(
            f"font-size: 22px; font-weight: 700; color: {color}; font-family: {_MONO};"
        )

        if next_label:
            self._next_label.setText(next_label)
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
        self._countdown_label.setText("Done")
        self._countdown_label.setStyleSheet(
            f"font-size: 18px; font-weight: 600; color: {_GREEN}; font-family: {_MONO};"
        )
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

    # ── Injection mode ────────────────────────────────────────────────────────

    def show_injection(self, channel: str, contact_sec: float, phase: str = "holding") -> None:
        """Switch overlay to injection contact-time mode.

        Replaces the cycle countdown with channel identity + contact countdown.
        The overlay stays visible and draggable — only its content changes.

        Args:
            channel:    Channel letter(s), e.g. "A" or "A, B"
            contact_sec: Total contact time in seconds (for initial display)
            phase:      "ready" (Phase 1 — pre-injection) or "holding" (Phase 2 — post-detection)
        """
        _GREEN = "#34C759"
        _BLUE  = "#007AFF"

        if phase == "ready":
            self._type_label.setText(f"Inject → {channel}")
            self._type_label.setStyleSheet(
                f"font-size: 13px; font-weight: 700; color: {_BLUE}; font-family: {_FONT};"
            )
        else:
            self._type_label.setText(f"Holding  {channel}")
            self._type_label.setStyleSheet(
                f"font-size: 13px; font-weight: 700; color: {_GREEN}; font-family: {_FONT};"
            )

        self._index_label.setText("contact")
        self._index_label.setStyleSheet(
            f"font-size: 12px; font-weight: 500; color: {_MUTED}; font-family: {_FONT};"
        )

        m, s = divmod(int(contact_sec), 60)
        self._countdown_label.setText(f"{m:02d}:{s:02d}")
        color = _GREEN if phase == "holding" else _BLUE
        self._countdown_label.setStyleSheet(
            f"font-size: 22px; font-weight: 700; color: {color}; font-family: {_MONO};"
        )

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

    def update_injection_countdown(self, remaining_sec: float) -> None:
        """Tick the contact-time countdown. Call every second from InjectionActionBar."""
        _GREEN = "#34C759"
        _WARN  = "#FF9500"
        _RED   = "#FF3B30"

        remaining_sec = max(0.0, remaining_sec)
        m, s = divmod(int(remaining_sec), 60)
        self._countdown_label.setText(f"{m:02d}:{s:02d}")

        if remaining_sec <= 10:
            color = _RED
        elif remaining_sec <= 30:
            color = _WARN
        else:
            color = _GREEN
        self._countdown_label.setStyleSheet(
            f"font-size: 22px; font-weight: 700; color: {color}; font-family: {_MONO};"
        )

    def update_binding_signal(
        self,
        response_label: str,
        response_color: str,
        slope_label: str,
        slope_color: str,
    ) -> None:
        """Show live binding quality signals in row 2 (during injection contact window).

        Hides the next-cycle hint and replaces it with binding response + slope.
        Call every second from _update_cycle_display while _injection_stats active.
        """
        self._next_label.setVisible(False)

        self._binding_label.setText(response_label)
        self._binding_label.setStyleSheet(
            f"font-size: 11px; font-weight: 600; color: {response_color}; font-family: {_MONO};"
        )
        self._binding_label.setVisible(bool(response_label))

        self._slope_label.setText(slope_label)
        self._slope_label.setStyleSheet(
            f"font-size: 10px; font-weight: 500; color: {slope_color}; font-family: {_MONO};"
        )
        self._slope_label.setVisible(bool(slope_label))
        self.adjustSize()

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

    def clear_injection(self) -> None:
        """Revert overlay back to normal cycle-countdown mode (called after wash)."""
        self._type_label.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {_TEXT}; font-family: {_FONT};"
        )
        self._index_label.setStyleSheet(
            f"font-size: 12px; font-weight: 500; color: {_MUTED}; font-family: {_FONT};"
        )
        self._countdown_label.setStyleSheet(
            f"font-size: 22px; font-weight: 700; color: {_ACCENT}; font-family: {_MONO};"
        )
        # Hide binding signal labels; update_status() repopulates row 2 on next tick
        self._binding_label.setVisible(False)
        self._slope_label.setVisible(False)

    def clear(self) -> None:
        """Hide the overlay when no cycle is running."""
        self.setVisible(False)
        self._user_moved = False  # reset so next cycle starts anchored top-right
        # reset type label color so it's correct next run
        self._type_label.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {_TEXT}; font-family: {_FONT};"
        )
        # reset binding signal labels
        self._binding_label.setVisible(False)
        self._slope_label.setVisible(False)
