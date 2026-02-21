"""RailTimerPopup — standalone countdown timer floating panel.

Launched from the IconRail timer button. Completely independent of the
experiment — no wash context, no cycle awareness. When the time is up,
the time is up.

Layout::

    ┌──────────────────────────┐
    │  Timer               ✕   │  ← drag handle
    ├──────────────────────────┤
    │         05:00            │  ← big countdown
    │   [1m][2m][5m][10m][15m] │  ← presets
    │  [   Start / Pause   ] [↺]│  ← controls
    └──────────────────────────┘

States: idle → running → paused → finished (alert)
"""

import logging

from PySide6.QtCore import QPoint, QTimer, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication, QFrame, QGraphicsDropShadowEffect,
    QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

logger = logging.getLogger(__name__)

_W = 240
_H = 250
_BG      = "#FFFFFF"
_HDR_BG  = "#F5F5F7"
_BORDER  = "#E5E5EA"
_TEXT    = "#1D1D1F"
_MUTED   = "#86868B"
_ACCENT  = "#2E30E3"
_WARN    = "#FF9500"
_FONT    = "-apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif"
_MONO    = "'SF Mono', 'Cascadia Code', 'Consolas', monospace"

_PRESETS = [("1m", 60), ("2m", 120), ("5m", 300), ("10m", 600), ("15m", 900)]


class RailTimerPopup(QFrame):
    """Floating countdown timer panel. Positioned by IconRail next to the timer button.

    Signals:
        timer_started(int)   — total seconds set
        timer_finished()     — countdown reached zero
    """

    timer_started  = Signal(int)
    timer_finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("RailTimerPopup")
        self.setFixedSize(_W, _H)
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)

        self._drag_offset = QPoint()
        self._total_seconds = 300       # default 5 min
        self._remaining    = 0
        self._state        = "idle"     # idle | running | paused | finished

        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(1000)
        self._tick_timer.timeout.connect(self._on_tick)

        self._alert_timer = QTimer(self)
        self._alert_timer.setInterval(600)
        self._alert_timer.timeout.connect(self._on_alert_blink)
        self._alert_phase = False

        self._setup_ui()
        self._update_display()
        self.hide()

    # ──────────────────────────────────────────────────────────────────────
    # UI construction
    # ──────────────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            QFrame#RailTimerPopup {{
                background: {_BG};
                border-radius: 14px;
                border: 1px solid {_BORDER};
            }}
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setColor(QColor(0, 0, 0, 55))
        shadow.setOffset(4, 4)
        self.setGraphicsEffect(shadow)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())
        root.addWidget(self._build_body(), 1)

    def _build_header(self) -> QFrame:
        hdr = QFrame()
        hdr.setFixedHeight(42)
        hdr.setStyleSheet(f"""
            QFrame {{
                background: {_HDR_BG};
                border-radius: 14px 14px 0 0;
                border-bottom: 1px solid {_BORDER};
            }}
        """)
        hdr.setCursor(Qt.CursorShape.SizeAllCursor)
        hdr.mousePressEvent = self._on_header_press
        hdr.mouseMoveEvent  = self._on_header_move

        row = QHBoxLayout(hdr)
        row.setContentsMargins(14, 0, 10, 0)
        row.setSpacing(8)

        lbl = QLabel("Timer")
        lbl.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {_TEXT};"
            f" font-family: {_FONT}; background: transparent; border: none;"
        )
        row.addWidget(lbl)
        row.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                color: {_MUTED}; font-size: 13px; border-radius: 12px;
            }}
            QPushButton:hover {{ background: {_BORDER}; color: {_TEXT}; }}
        """)
        close_btn.clicked.connect(self.hide)
        row.addWidget(close_btn)
        return hdr

    def _build_body(self) -> QWidget:
        body = QWidget()
        body.setStyleSheet(f"background: {_BG}; border: none;")
        col = QVBoxLayout(body)
        col.setContentsMargins(14, 10, 14, 14)
        col.setSpacing(10)

        # ── Big countdown ─────────────────────────────────────────────────
        self._display = QLabel("05:00")
        self._display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._display.setStyleSheet(
            f"font-size: 44px; font-weight: 300; letter-spacing: 2px;"
            f" color: {_TEXT}; font-family: {_MONO};"
            f" background: transparent; border: none;"
        )
        col.addWidget(self._display)

        # ── Presets ───────────────────────────────────────────────────────
        preset_row = QHBoxLayout()
        preset_row.setSpacing(5)
        preset_row.setContentsMargins(0, 0, 0, 0)
        self._preset_btns: list[QPushButton] = []
        for label, secs in _PRESETS:
            btn = QPushButton(label)
            btn.setFixedHeight(24)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(self._chip_style(active=False))
            btn.clicked.connect(lambda _checked, s=secs: self._on_preset(s))
            preset_row.addWidget(btn)
            self._preset_btns.append(btn)
        col.addLayout(preset_row)

        # Highlight the default preset
        self._highlight_preset(self._total_seconds)

        # ── Controls ──────────────────────────────────────────────────────
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(6)
        ctrl_row.setContentsMargins(0, 0, 0, 0)

        self._start_btn = QPushButton("Start")
        self._start_btn.setFixedHeight(32)
        self._start_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._start_btn.setStyleSheet(
            f"QPushButton {{ background: {_ACCENT}; color: #FFF; border: none;"
            f" border-radius: 8px; font-size: 13px; font-weight: 600; font-family: {_FONT}; }}"
            f"QPushButton:hover {{ background: #2325C4; }}"
            f"QPushButton:pressed {{ background: #1D1FA0; }}"
        )
        self._start_btn.clicked.connect(self._on_start_pause)
        ctrl_row.addWidget(self._start_btn)

        reset_btn = QPushButton("↺")
        reset_btn.setFixedSize(32, 32)
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_btn.setToolTip("Reset to selected duration")
        reset_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {_MUTED}; border: 1.5px solid {_BORDER};"
            f" border-radius: 8px; font-size: 18px; }}"
            f"QPushButton:hover {{ background: {_HDR_BG}; color: {_TEXT}; }}"
        )
        reset_btn.clicked.connect(self._on_reset)
        ctrl_row.addWidget(reset_btn)

        col.addLayout(ctrl_row)
        return body

    # ──────────────────────────────────────────────────────────────────────
    # State machine
    # ──────────────────────────────────────────────────────────────────────

    def _on_preset(self, seconds: int) -> None:
        self._total_seconds = seconds
        self._highlight_preset(seconds)
        self._on_reset()

    def _on_start_pause(self) -> None:
        if self._state == "idle":
            self._remaining = self._total_seconds
            self._state = "running"
            self._tick_timer.start()
            self.timer_started.emit(self._total_seconds)
        elif self._state == "running":
            self._tick_timer.stop()
            self._state = "paused"
        elif self._state == "paused":
            self._tick_timer.start()
            self._state = "running"
        elif self._state == "finished":
            self._stop_alert()
            self._state = "idle"
        self._update_display()

    def _on_reset(self) -> None:
        self._tick_timer.stop()
        self._stop_alert()
        self._remaining = self._total_seconds
        self._state = "idle"
        self._update_display()

    def _on_tick(self) -> None:
        if self._remaining > 0:
            self._remaining -= 1
            self._update_display()
        if self._remaining == 0:
            self._tick_timer.stop()
            self._state = "finished"
            self._trigger_alert()
            self._update_display()

    # ──────────────────────────────────────────────────────────────────────
    # Alert
    # ──────────────────────────────────────────────────────────────────────

    def _trigger_alert(self) -> None:
        self.timer_finished.emit()
        self._alert_phase = False
        self._alert_timer.start()
        try:
            QApplication.beep()
        except Exception:
            pass

    def _on_alert_blink(self) -> None:
        self._alert_phase = not self._alert_phase
        if self._alert_phase:
            self._display.setStyleSheet(
                f"font-size: 44px; font-weight: 300; letter-spacing: 2px;"
                f" color: {_WARN}; font-family: {_MONO};"
                f" background: transparent; border: none;"
            )
        else:
            self._display.setStyleSheet(
                f"font-size: 44px; font-weight: 300; letter-spacing: 2px;"
                f" color: {_TEXT}; font-family: {_MONO};"
                f" background: transparent; border: none;"
            )

    def _stop_alert(self) -> None:
        self._alert_timer.stop()
        self._display.setStyleSheet(
            f"font-size: 44px; font-weight: 300; letter-spacing: 2px;"
            f" color: {_TEXT}; font-family: {_MONO};"
            f" background: transparent; border: none;"
        )

    # ──────────────────────────────────────────────────────────────────────
    # Display
    # ──────────────────────────────────────────────────────────────────────

    def _update_display(self) -> None:
        secs = self._remaining if self._state != "idle" else self._total_seconds
        m, s = divmod(secs, 60)
        self._display.setText(f"{m:02d}:{s:02d}")

        if self._state == "idle":
            self._start_btn.setText("Start")
            self._start_btn.setStyleSheet(
                f"QPushButton {{ background: {_ACCENT}; color: #FFF; border: none;"
                f" border-radius: 8px; font-size: 13px; font-weight: 600; font-family: {_FONT}; }}"
                f"QPushButton:hover {{ background: #2325C4; }}"
            )
        elif self._state == "running":
            self._start_btn.setText("Pause")
            self._start_btn.setStyleSheet(
                f"QPushButton {{ background: rgba(46,48,227,0.10); color: {_ACCENT};"
                f" border: 1.5px solid {_ACCENT}; border-radius: 8px;"
                f" font-size: 13px; font-weight: 600; font-family: {_FONT}; }}"
                f"QPushButton:hover {{ background: rgba(46,48,227,0.16); }}"
            )
        elif self._state == "paused":
            self._start_btn.setText("Resume")
            self._start_btn.setStyleSheet(
                f"QPushButton {{ background: rgba(255,149,0,0.12); color: {_WARN};"
                f" border: 1.5px solid {_WARN}; border-radius: 8px;"
                f" font-size: 13px; font-weight: 600; font-family: {_FONT}; }}"
                f"QPushButton:hover {{ background: rgba(255,149,0,0.20); }}"
            )
        elif self._state == "finished":
            self._start_btn.setText("Dismiss")
            self._start_btn.setStyleSheet(
                f"QPushButton {{ background: {_WARN}; color: #FFF; border: none;"
                f" border-radius: 8px; font-size: 13px; font-weight: 600; font-family: {_FONT}; }}"
                f"QPushButton:hover {{ background: #E08600; }}"
            )

    def _highlight_preset(self, seconds: int) -> None:
        for btn, (_, secs) in zip(self._preset_btns, _PRESETS):
            btn.setStyleSheet(self._chip_style(active=(secs == seconds)))

    @staticmethod
    def _chip_style(active: bool) -> str:
        if active:
            return (
                f"QPushButton {{ background: {_ACCENT}; color: #FFF; border: none;"
                f" border-radius: 6px; font-size: 11px; font-weight: 600; font-family: {_FONT}; }}"
            )
        return (
            f"QPushButton {{ background: {_HDR_BG}; color: {_MUTED}; border: 1px solid {_BORDER};"
            f" border-radius: 6px; font-size: 11px; font-weight: 500; font-family: {_FONT}; }}"
            f"QPushButton:hover {{ background: {_BORDER}; color: {_TEXT}; }}"
        )

    # ──────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────

    def toggle_at(self, global_pos: "QPoint") -> None:
        """Show/hide positioned to the right of global_pos."""
        if self.isVisible():
            self.hide()
            return
        # Position popup to the right of the icon rail button
        self.move(global_pos.x() + 4, global_pos.y() - _H // 2)
        self.show()
        self.raise_()

    @property
    def is_running(self) -> bool:
        return self._state == "running"

    @property
    def is_finished(self) -> bool:
        return self._state == "finished"

    # ──────────────────────────────────────────────────────────────────────
    # Drag
    # ──────────────────────────────────────────────────────────────────────

    def _on_header_press(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def _on_header_move(self, event) -> None:
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
