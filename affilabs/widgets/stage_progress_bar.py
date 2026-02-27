"""StageProgressBar — slim 24px horizontal progress spine below the TransportBar.

6 stages shown as dots connected by a line:
    ●────●────○────○────○────○
  Connect Calibrate Method Record Edit Export

States per dot:
    completed  — filled green  (#34C759)
    active     — filled blue   (#2E30E3), pulsing opacity animation
    pending    — empty circle  (#C7C7CC)

Hover over any dot → a small label chip floats above it showing the stage name
(and "✓" if completed). No Qt tooltip delay — custom enterEvent on each dot.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import (
    QEasingCurve, QPoint, QPropertyAnimation, QSize, Qt, QTimer,
)
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

logger = logging.getLogger(__name__)

# ── Stage definitions (order matters) ────────────────────────────────────────

STAGES: list[str] = ["connect", "calibrate", "method", "record", "edit", "export"]

_LABELS: dict[str, str] = {
    "connect":   "Connect",
    "calibrate": "Calibrate",
    "method":    "Method",
    "record":    "Record",
    "edit":      "Edit",
    "export":    "Export",
}

# ── Colours ───────────────────────────────────────────────────────────────────

_COL_DONE    = QColor("#34C759")   # green — completed
_COL_ACTIVE  = QColor("#2E30E3")   # blue  — current
_COL_PENDING = QColor("#C7C7CC")   # gray  — not yet reached
_COL_LINE    = QColor("#D5D5D7")   # connector line

_DOT_R   = 5    # dot radius px
_HEIGHT  = 24   # strip height px


# ── Dot widget ────────────────────────────────────────────────────────────────

class _StageDot(QWidget):
    """Single 16×16px circular dot with hover label."""

    def __init__(self, stage: str, label_widget: QLabel, parent: QWidget) -> None:
        super().__init__(parent)
        self._stage = stage
        self._label_widget = label_widget   # shared floating label owned by StageProgressBar
        self._state: str = "pending"        # "pending" | "active" | "completed"
        self.setFixedSize(16, 16)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def set_state(self, state: str) -> None:
        if state != self._state:
            self._state = state
            self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = self.width() // 2, self.height() // 2

        if self._state == "completed":
            p.setBrush(_COL_DONE)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPoint(cx, cy), _DOT_R, _DOT_R)
        elif self._state == "active":
            p.setBrush(_COL_ACTIVE)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPoint(cx, cy), _DOT_R, _DOT_R)
        else:  # pending
            pen = QPen(_COL_PENDING, 1.5)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPoint(cx, cy), _DOT_R - 1, _DOT_R - 1)

    def enterEvent(self, _event) -> None:
        name = _LABELS.get(self._stage, self._stage.capitalize())
        suffix = " ✓" if self._state == "completed" else (" ←" if self._state == "active" else "")
        self._label_widget.setText(f"{name}{suffix}")

        # Position the label centred above this dot in parent coordinates
        dot_pos = self.mapTo(self.parent(), QPoint(self.width() // 2, 0))
        lw = self._label_widget
        lw.adjustSize()
        x = dot_pos.x() - lw.width() // 2
        y = dot_pos.y() - lw.height() - 2
        lw.move(max(0, x), max(0, y))
        lw.raise_()
        lw.show()

    def leaveEvent(self, _event) -> None:
        self._label_widget.hide()


# ── Main bar ──────────────────────────────────────────────────────────────────

class StageProgressBar(QWidget):
    """24px horizontal strip with 6 stage dots + connecting lines.

    Public API
    ----------
    advance_to(stage)  — mark all stages up to and including `stage` as
                         completed; mark the *next* stage as active.
                         Call with the stage that just completed, e.g.
                         advance_to("connect") after hardware connects.
    reset()            — return all dots to pending (app disconnected).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(_HEIGHT)
        self.setObjectName("StageProgressBar")
        self.setStyleSheet(
            "QWidget#StageProgressBar { background: #F5F5F7; "
            "border-bottom: 1px solid #E5E5EA; }"
        )

        # Shared floating hover label (child of this widget, drawn above dots)
        self._hover_label = QLabel(self)
        self._hover_label.setStyleSheet(
            "background: rgba(29,29,31,0.82); color: white;"
            "border-radius: 4px; padding: 2px 7px;"
            "font-size: 11px; font-weight: 500;"
        )
        self._hover_label.hide()
        self._hover_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        # Layout: stretch | dot | spacer | dot | … | stretch
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 0, 24, 0)
        layout.setSpacing(0)
        layout.addStretch(1)

        self._dots: dict[str, _StageDot] = {}

        for i, stage in enumerate(STAGES):
            dot = _StageDot(stage, self._hover_label, self)
            self._dots[stage] = dot
            layout.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)
            if i < len(STAGES) - 1:
                layout.addStretch(1)   # equal spacing between dots

        layout.addStretch(1)

        # Pulse animation on the active dot (opacity via window opacity trick
        # is too blunt — we use a QTimer to repaint with alternating alpha)
        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(600)
        self._pulse_timer.timeout.connect(self._on_pulse_tick)
        self._pulse_bright = True
        self._active_stage: str | None = None

    # ── Public API ────────────────────────────────────────────────────────────

    def advance_to(self, completed_stage: str) -> None:
        """Mark `completed_stage` (and all prior) as done; next as active."""
        if completed_stage not in STAGES:
            logger.warning(f"StageProgressBar: unknown stage {completed_stage!r}")
            return

        idx = STAGES.index(completed_stage)

        for i, stage in enumerate(STAGES):
            if i <= idx:
                self._dots[stage].set_state("completed")
            elif i == idx + 1:
                self._dots[stage].set_state("active")
                self._active_stage = stage
            else:
                self._dots[stage].set_state("pending")

        self._pulse_timer.start()
        self.update()

    def reset(self) -> None:
        """Return all dots to pending (call on hardware disconnect)."""
        self._pulse_timer.stop()
        self._active_stage = None
        for dot in self._dots.values():
            dot.set_state("pending")
        self.update()

    # ── Line drawing ──────────────────────────────────────────────────────────

    def paintEvent(self, _event) -> None:
        """Draw connecting lines between dots."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        dot_list = [self._dots[s] for s in STAGES]
        cy = self.height() // 2

        for i in range(len(dot_list) - 1):
            left_dot  = dot_list[i]
            right_dot = dot_list[i + 1]

            # x positions in bar coordinates
            x1 = left_dot.x()  + left_dot.width()  // 2 + _DOT_R
            x2 = right_dot.x() + right_dot.width() // 2 - _DOT_R

            left_state  = left_dot._state
            right_state = right_dot._state

            if left_state == "completed" and right_state in ("completed", "active"):
                color = _COL_DONE
            else:
                color = _COL_LINE

            pen = QPen(color, 1.5)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.drawLine(x1, cy, x2, cy)

    # ── Pulse tick ────────────────────────────────────────────────────────────

    def _on_pulse_tick(self) -> None:
        """Toggle active dot between full and 60% opacity via repaint."""
        if self._active_stage and self._active_stage in self._dots:
            dot = self._dots[self._active_stage]
            self._pulse_bright = not self._pulse_bright
            dot.setWindowOpacity(1.0 if self._pulse_bright else 0.55)
            dot.update()
