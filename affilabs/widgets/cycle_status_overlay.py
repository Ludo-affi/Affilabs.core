"""CycleStatusOverlay — live-cycle status embedded inside the Active Cycle graph.

Positioned top-right of the PlotWidget by _position_cycle_status_overlay().
Shown automatically when a cycle starts, hidden when it ends.

Layout::

    ┌─ Binding ─────── 2 / 5 ─┐
    │  02:30   Next: Rinse     │
    └──────────────────────────┘
"""

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

logger = logging.getLogger(__name__)

_FONT = "-apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif"
_MONO = "'SF Mono', 'Cascadia Code', 'Consolas', monospace"
_ACCENT = "#2E30E3"
_WARN = "#FF9500"
_MUTED = "#86868B"
_TEXT = "#1D1D1F"


class CycleStatusOverlay(QWidget):
    """Compact cycle-progress chip embedded inside the Active Cycle PlotWidget.

    Call ``update_status(...)`` every second from ``_update_cycle_display``.
    Call ``clear()`` when the cycle ends.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CycleStatusOverlay")
        # Allow mouse events (don't block interaction with the graph behind it)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setVisible(False)  # Hidden until a cycle starts
        self._init_ui()

    # ── UI construction ──────────────────────────────────────────────────

    def _init_ui(self):
        self.setStyleSheet(
            "QWidget#CycleStatusOverlay {"
            "  background: rgba(255, 255, 255, 0.88);"
            "  border: 1px solid rgba(0, 0, 0, 0.10);"
            "  border-radius: 8px;"
            "}"
            "QWidget#CycleStatusOverlay QLabel {"
            "  background: transparent;"
            "  border: none;"
            "}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 6)
        root.setSpacing(2)

        # ── Row 1: type badge + cycle index ──────────────────────────────
        row1 = QHBoxLayout()
        row1.setSpacing(6)
        row1.setContentsMargins(0, 0, 0, 0)

        self._type_label = QLabel("—")
        self._type_label.setStyleSheet(
            f"font-size: 11px; font-weight: 700; color: {_TEXT}; font-family: {_FONT};"
        )
        row1.addWidget(self._type_label)

        row1.addStretch()

        self._index_label = QLabel("")
        self._index_label.setStyleSheet(
            f"font-size: 10px; font-weight: 500; color: {_MUTED}; font-family: {_FONT};"
        )
        row1.addWidget(self._index_label)

        root.addLayout(row1)

        # ── Row 2: countdown + next-cycle hint ───────────────────────────
        row2 = QHBoxLayout()
        row2.setSpacing(8)
        row2.setContentsMargins(0, 0, 0, 0)

        self._countdown_label = QLabel("00:00")
        self._countdown_label.setStyleSheet(
            f"font-size: 18px; font-weight: 700; color: {_ACCENT}; font-family: {_MONO};"
        )
        row2.addWidget(self._countdown_label)

        row2.addStretch()

        self._next_label = QLabel("")
        self._next_label.setStyleSheet(
            f"font-size: 10px; font-weight: 500; color: {_MUTED}; font-family: {_FONT};"
        )
        self._next_label.setVisible(False)
        row2.addWidget(self._next_label)

        root.addLayout(row2)

        self.adjustSize()

    # ── Public API ───────────────────────────────────────────────────────

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
            f"font-size: 18px; font-weight: 700; color: {color}; font-family: {_MONO};"
        )

        if next_label:
            self._next_label.setText(next_label)
            self._next_label.setVisible(True)
        else:
            self._next_label.setVisible(False)

        if not self.isVisible():
            self.setVisible(True)

        # Re-anchor to top-right of parent each tick (handles resize)
        parent = self.parentWidget()
        if parent is not None:
            self.adjustSize()
            x = max(62, parent.width() - self.width() - 10)
            self.move(x, 10)

        self.raise_()

    def clear(self) -> None:
        """Hide the overlay when no cycle is running."""
        self.setVisible(False)
