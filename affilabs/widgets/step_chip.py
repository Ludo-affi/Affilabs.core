"""StepChip — compact 'Step N / 6' pill in the TransportBar.

Clicking the chip toggles a floating popover that shows all 6 experiment
stages as a mini checklist.  The popover auto-dismisses on outside click.

Public API
----------
StepChip.advance_to(completed_stage)   — mirror of StageProgressBar API
StepChip.reset()                        — reset to step 0

Stages (order matters):
    connect → calibrate → method → record → edit → export
"""
from __future__ import annotations

import logging
from PySide6.QtCore import Qt, QPoint, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)

logger = logging.getLogger(__name__)

# ── Stage definitions ─────────────────────────────────────────────────────────

_STAGES: list[str] = ["connect", "calibrate", "method", "record", "edit", "export"]
_SHORT:  dict[str, str] = {
    "connect":   "Connect",
    "calibrate": "Calibrate",
    "method":    "Method",
    "record":    "Experiment",
    "edit":      "Analyse",
    "export":    "Export",
}
_LABELS: dict[str, str] = {
    "connect":   "Connect hardware",
    "calibrate": "Calibrate sensors",
    "method":    "Build a method",
    "record":    "Run experiment",
    "edit":      "Review & edit data",
    "export":    "Export results",
}

_COL_DONE    = "#34C759"   # green
_COL_ACTIVE  = "#007AFF"   # blue
_COL_PENDING = "#C7C7CC"   # gray


# ── Popover ───────────────────────────────────────────────────────────────────

class _StepsPopover(QFrame):
    """Floating frameless panel listing all 6 stages."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setObjectName("StepsPopover")
        self.setStyleSheet(
            "QFrame#StepsPopover {"
            "  background: white;"
            "  border: 1px solid rgba(0,0,0,0.12);"
            "  border-radius: 10px;"
            "}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(0)

        # Header
        header = QLabel("Experiment workflow")
        header.setStyleSheet(
            "font-size: 11px; font-weight: 700; color: #6E6E73;"
            "letter-spacing: 0.4px; text-transform: uppercase;"
            "background: transparent; margin-bottom: 10px;"
        )
        layout.addWidget(header)
        layout.addSpacing(8)

        self._rows: dict[str, QLabel] = {}

        for stage in _STAGES:
            row = QHBoxLayout()
            row.setSpacing(10)
            row.setContentsMargins(0, 0, 0, 0)

            # Dot indicator
            dot = QLabel("●")
            dot.setFixedWidth(14)
            dot.setObjectName(f"dot_{stage}")
            dot.setStyleSheet(f"color: {_COL_PENDING}; background: transparent; font-size: 10px;")
            dot.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter)

            # Label
            lbl = QLabel(_LABELS[stage])
            lbl.setObjectName(f"lbl_{stage}")
            lbl.setStyleSheet(
                f"color: #86868B; background: transparent;"
                "font-size: 13px; font-weight: 400;"
                "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            )

            row.addWidget(dot)
            row.addWidget(lbl)
            row.addStretch()
            layout.addLayout(row)
            layout.addSpacing(6)

            self._rows[stage] = (dot, lbl)  # type: ignore[assignment]

        layout.addSpacing(2)
        self.adjustSize()

    def update_progress(self, completed_up_to: int) -> None:
        """Color rows: completed=green, active=blue, pending=gray.

        completed_up_to: index of the last completed stage (-1 = none done)
        """
        for i, stage in enumerate(_STAGES):
            dot, lbl = self._rows[stage]
            if i <= completed_up_to:
                color = _COL_DONE
                text_color = "#1D1D1F"
                weight = "600"
                glyph = "✓"
            elif i == completed_up_to + 1:
                color = _COL_ACTIVE
                text_color = "#1D1D1F"
                weight = "600"
                glyph = "●"
            else:
                color = _COL_PENDING
                text_color = "#86868B"
                weight = "400"
                glyph = "●"

            dot.setStyleSheet(
                f"color: {color}; background: transparent; font-size: 10px;"
            )
            dot.setText(glyph)
            lbl.setStyleSheet(
                f"color: {text_color}; background: transparent;"
                f"font-size: 13px; font-weight: {weight};"
                "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            )

    def show_below(self, chip: QWidget) -> None:
        """Position below `chip` and show."""
        global_pos = chip.mapToGlobal(QPoint(0, chip.height() + 4))
        self.move(global_pos)
        self.adjustSize()
        self.show()
        self.raise_()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self.hide()
        super().mousePressEvent(event)


# ── Chip pill ─────────────────────────────────────────────────────────────────

class StepChip(QWidget):
    """Mini workflow-progress tracker for the TransportBar.

    Shows 6 coloured dots (done=green, active=blue, pending=gray) plus
    the current stage name.  Click anywhere to open the stage-list popover.

    Call advance_to(stage) / reset() to sync state with StageProgressBar.
    """

    _COL_FRAME_BG     = "rgba(0,0,0,0.05)"
    _COL_FRAME_BORDER = "rgba(0,0,0,0.09)"
    _COL_FRAME_HOVER  = "rgba(0,0,0,0.09)"

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._completed_idx: int = -1  # -1 = nothing done yet
        self._popover: _StepsPopover | None = None
        self._popover_open: bool = False

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Experiment workflow · click to see all steps")

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Pill frame
        self._frame = QFrame()
        self._frame.setObjectName("StepChipFrame")
        self._frame.setFixedHeight(26)
        self._apply_frame_style(False)

        fl = QHBoxLayout(self._frame)
        fl.setContentsMargins(8, 0, 10, 0)
        fl.setSpacing(4)

        # 6 progress dots
        self._dots: list[QLabel] = []
        for _ in range(6):
            dot = QLabel()
            dot.setFixedSize(6, 6)
            dot.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            dot.setStyleSheet("background: #D1D1D6; border-radius: 3px;")
            fl.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)
            self._dots.append(dot)

        # Thin vertical separator
        sep = QLabel()
        sep.setFixedSize(1, 12)
        sep.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        sep.setStyleSheet("background: rgba(0,0,0,0.12); margin: 0 2px;")
        fl.addWidget(sep, 0, Qt.AlignmentFlag.AlignVCenter)

        # Stage name
        self._name_lbl = QLabel()
        self._name_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._name_lbl.setStyleSheet(
            "color: #3C3C43; font-size: 11px; font-weight: 600; background: transparent;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        fl.addWidget(self._name_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        outer.addWidget(self._frame)
        self._update_display()

    # ── Public API ────────────────────────────────────────────────────────────

    def advance_to(self, completed_stage: str) -> None:
        if completed_stage not in _STAGES:
            return
        self._completed_idx = _STAGES.index(completed_stage)
        self._update_display()
        if self._popover and self._popover.isVisible():
            self._popover.update_progress(self._completed_idx)

    def reset(self) -> None:
        self._completed_idx = -1
        self._update_display()
        if self._popover:
            self._popover.hide()
            self._popover.update_progress(-1)
        self._popover_open = False

    # ── Internals ─────────────────────────────────────────────────────────────

    def _apply_frame_style(self, hovered: bool) -> None:
        bg = self._COL_FRAME_HOVER if hovered else self._COL_FRAME_BG
        self._frame.setStyleSheet(
            f"QFrame#StepChipFrame {{"
            f"  background: {bg};"
            f"  border: 1px solid {self._COL_FRAME_BORDER};"
            f"  border-radius: 13px;"
            f"}}"
        )

    def _update_display(self) -> None:
        n = len(_STAGES)
        for i, dot in enumerate(self._dots):
            if i <= self._completed_idx:
                dot.setStyleSheet("background: #34C759; border-radius: 3px;")   # done
            elif i == self._completed_idx + 1:
                dot.setStyleSheet("background: #007AFF; border-radius: 3px;")   # active
            else:
                dot.setStyleSheet("background: #D1D1D6; border-radius: 3px;")   # pending

        if self._completed_idx >= n - 1:
            self._name_lbl.setText("Done")
            self._name_lbl.setStyleSheet(
                "color: #34C759; font-size: 11px; font-weight: 600; background: transparent;"
                "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            )
        else:
            active_idx = self._completed_idx + 1
            stage = _STAGES[active_idx]
            self._name_lbl.setText(_SHORT[stage])
            self._name_lbl.setStyleSheet(
                "color: #3C3C43; font-size: 11px; font-weight: 600; background: transparent;"
                "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            )

    def _ensure_popover(self) -> _StepsPopover:
        if self._popover is None:
            top = self.window()
            self._popover = _StepsPopover(top)
            self._popover.update_progress(self._completed_idx)
        return self._popover

    def _toggle_popover(self) -> None:
        popover = self._ensure_popover()
        if self._popover_open:
            popover.hide()
            self._popover_open = False
        else:
            popover.update_progress(self._completed_idx)
            popover.show_below(self._frame)
            self._popover_open = True
            QTimer.singleShot(50, self._install_dismiss_filter)

    def _install_dismiss_filter(self) -> None:
        try:
            QApplication.instance().installEventFilter(self)
        except Exception:
            pass

    # ── Qt event overrides ────────────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self._toggle_popover()
        super().mousePressEvent(event)

    def enterEvent(self, event) -> None:  # noqa: N802
        self._apply_frame_style(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._apply_frame_style(False)
        super().leaveEvent(event)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.Type.MouseButtonPress:
            popover = self._popover
            if popover and popover.isVisible():
                try:
                    global_pos = event.globalPosition().toPoint()
                    if not popover.geometry().contains(global_pos):
                        popover.hide()
                        self._popover_open = False
                        QApplication.instance().removeEventFilter(self)
                except Exception:
                    pass
        return False
