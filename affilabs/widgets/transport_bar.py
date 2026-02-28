"""TransportBar — slim 44px horizontal action strip replacing the nav bar.

Layout (left → right):
  [Live] [Edits]  gap  [+ Method]  stretch  [~ Spectrum] [✦ Spark] [⏱ Timer]
  [⏸ Pause] [● Rec] [⏻ Power]  logo

All main_window.* button attributes are set directly on main_window so that
acquisition_mixin, timer_mixin, etc. find them unchanged.
"""

import logging
from typing import Optional

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QWidget,
)

from affilabs.utils.resource_path import get_affilabs_resource

logger = logging.getLogger(__name__)

# ─── Style constants ──────────────────────────────────────────────────────────
_BG = "#FFFFFF"
_ACCENT = "rgba(46, 48, 227, {a})"
_BTN_BASE = (
    "QPushButton {{"
    "  background: rgba(46, 48, 227, 0.08);"
    "  border: 1px solid rgba(46, 48, 227, 0.25);"
    "  border-radius: 8px;"
    "  padding: 0px;"
    "}}"
    "QPushButton:hover {{"
    "  background: rgba(46, 48, 227, 0.14);"
    "  border: 1px solid rgba(46, 48, 227, 0.40);"
    "}}"
    "QPushButton:pressed {{ background: rgba(46, 48, 227, 0.22); }}"
    "QPushButton:disabled {{"
    "  background: rgba(46, 48, 227, 0.06);"
    "  border: 1px solid rgba(46, 48, 227, 0.10);"
    "}}"
)

_HEIGHT = 56
_BTN_W = 36   # icon buttons
_BTN_H = 36


def _svg_icon(svg_text: str, color_off: str, color_on: Optional[str] = None) -> QIcon:
    """Render an inline SVG string into a QIcon with optional checked state."""
    icon = QIcon()

    def _render(color: str) -> QPixmap:
        svg = svg_text.replace("currentColor", color)
        renderer = QSvgRenderer(svg.encode("utf-8"))
        px = QPixmap(QSize(20, 20))
        px.fill(Qt.GlobalColor.transparent)
        p = QPainter(px)
        renderer.render(p)
        p.end()
        return px

    icon.addPixmap(_render(color_off), QIcon.Mode.Normal, QIcon.State.Off)
    if color_on:
        icon.addPixmap(_render(color_on), QIcon.Mode.Normal, QIcon.State.On)
    return icon


class TransportBar(QWidget):
    """Full-width 44px action strip at the top of the workspace.

    After construction all button attributes are available on this object AND
    set on main_window so existing code keeps working unchanged.
    """

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setFixedHeight(_HEIGHT)
        self.setObjectName("TransportBar")
        self.setStyleSheet(
            f"QWidget#TransportBar {{ background: {_BG}; }}"
            "QWidget#TransportBar > QFrame#sep {"
            "  background: #E5E5EA; min-width: 1px; max-width: 1px; margin: 6px 0;"
            "}"
        )

        self._nav_buttons: list[QPushButton] = []
        self._build()

    # ──────────────────────────────────────────────────────────────────────────
    # Construction
    # ──────────────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(6)

        # ── Power button ──────────────────────────────────────────────────────
        self.power_btn = QPushButton()
        self.power_btn.setFixedSize(_BTN_W, _BTN_H)
        self.power_btn.setProperty("powerState", "disconnected")
        power_svg = get_affilabs_resource("ui/img/power_icon.svg")
        if power_svg and power_svg.exists():
            self.power_btn.setIcon(QIcon(str(power_svg)))
            self.power_btn.setIconSize(QSize(22, 22))
        else:
            self.power_btn.setText("⏻")
        self.power_btn.setStyleSheet(
            "QPushButton {"
            "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1,"
            "    stop:0 rgba(29,29,31,0.4), stop:1 rgba(29,29,31,0.5));"
            "  color: white;"
            "  border: 1px solid rgba(29,29,31,0.2);"
            "  border-radius: 16px;"
            "  padding: 0px;"
            "}"
            "QPushButton:hover {"
            "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1,"
            "    stop:0 rgba(29,29,31,0.5), stop:1 rgba(29,29,31,0.6));"
            "  border: 1px solid rgba(29,29,31,0.3);"
            "}"
        )
        self.power_btn.setToolTip(
            "Power On Device (Ctrl+P)\n"
            "Red = Disconnected  |  Yellow = Searching  |  Green = Connected"
        )
        self.power_btn.clicked.connect(self.main_window._handle_power_click)
        self.main_window.power_btn = self.power_btn
        layout.addWidget(self.power_btn)

        layout.addSpacing(8)
        layout.addWidget(self._sep())
        layout.addSpacing(8)

        # ── Tab switcher pills ────────────────────────────────────────────────
        nav_configs = [
            ("Live",  0, "Real-time data visualisation"),
            ("Edits", 1, "Edit and annotate experiment data"),
            ("Notes", 2, "Experiment history and lab notebook"),
        ]
        for i, (label, idx, tip) in enumerate(nav_configs):
            btn = QPushButton(label)
            btn.setFixedHeight(32)
            btn.setMinimumWidth(80)
            btn.setCheckable(True)
            btn.setChecked(i == 0)
            btn.setToolTip(tip)
            btn.setStyleSheet(
                "QPushButton {"
                "  background: rgba(46, 48, 227, 0.08);"
                "  color: rgb(46, 48, 227);"
                "  border: none;"
                "  border-radius: 16px;"
                "  padding: 4px 18px;"
                "  font-size: 13px;"
                "  font-weight: 500;"
                "}"
                "QPushButton:hover { background: rgba(46, 48, 227, 0.16); }"
                "QPushButton:checked {"
                "  background: rgb(46, 48, 227);"
                "  color: white;"
                "  font-weight: 600;"
                "}"
            )
            btn.clicked.connect(
                lambda _checked, page=idx: self.main_window.navigation_presenter.switch_page(page)
            )
            self._nav_buttons.append(btn)
            layout.addWidget(btn)

        # Keep reference on main window so switch_page() can update checked states
        self.main_window.navigation_presenter.nav_buttons = self._nav_buttons

        layout.addSpacing(12)

        # ── Step progress chip ────────────────────────────────────────────────
        from affilabs.widgets.step_chip import StepChip  # local import avoids circular
        self.step_chip = StepChip(self)
        layout.addWidget(self.step_chip)

        layout.addStretch(1)

        # ── + Method button ───────────────────────────────────────────────────
        self.build_method_btn = QPushButton("+ Method")
        self.build_method_btn.setFixedHeight(32)
        self.build_method_btn.setMinimumWidth(88)
        self.build_method_btn.setToolTip("Build Method — design and queue experiment cycles")
        self.build_method_btn.setStyleSheet(
            "QPushButton {"
            "  background: transparent;"
            "  color: rgb(46, 48, 227);"
            "  border: 1.5px solid rgba(46, 48, 227, 0.55);"
            "  border-radius: 16px;"
            "  padding: 4px 14px;"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "}"
            "QPushButton:hover {"
            "  background: rgba(46, 48, 227, 0.08);"
            "  border-color: rgba(46, 48, 227, 0.80);"
            "}"
            "QPushButton:pressed { background: rgba(46, 48, 227, 0.14); }"
            "QPushButton:disabled { color: rgba(46,48,227,0.30); border-color: rgba(46,48,227,0.18); }"
        )
        layout.addWidget(self.build_method_btn)

        layout.addSpacing(4)
        layout.addWidget(self._sep())
        layout.addSpacing(4)

        # ── Queue toggle ──────────────────────────────────────────────────────
        _queue_svg_path = get_affilabs_resource("ui/img/queue_icon.svg")
        _queue_svg = (
            _queue_svg_path.read_text(encoding="utf-8")
            if _queue_svg_path and _queue_svg_path.exists()
            else (
                '<svg width="24" height="24" viewBox="0 0 24 24" fill="none">'
                '<path d="M4 7h16" stroke="currentColor" stroke-width="1.75" stroke-linecap="round"/>'
                '<path d="M4 12h16" stroke="currentColor" stroke-width="1.75" stroke-linecap="round"/>'
                '<path d="M4 17h10" stroke="currentColor" stroke-width="1.75" stroke-linecap="round"/>'
                '</svg>'
            )
        )
        self.queue_toggle_btn = self._icon_btn(
            icon=_svg_icon(_queue_svg, "#2E30E3", "#FFFFFF"),
            tip="Show / hide Run Queue panel  (Ctrl+Q)",
            checkable=True,
            style_override=(
                "QPushButton { background: rgba(46,48,227,0.08); border: 1.5px solid rgba(46,48,227,0.30); border-radius: 8px; }"
                "QPushButton:hover { background: rgba(46,48,227,0.16); border-color: rgba(46,48,227,0.60); }"
                "QPushButton:checked { background: rgba(46,48,227,0.85); border-color: rgba(46,48,227,1.0); }"
                "QPushButton:checked:hover { background: #2E30E3; border-color: #2E30E3; }"
            ),
        )
        self.queue_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.queue_toggle_btn.toggled.connect(self.main_window._on_toggle_queue_panel)
        self.main_window._live_queue_btn = self.queue_toggle_btn
        layout.addWidget(self.queue_toggle_btn)

        layout.addSpacing(4)

        # ── Spark toggle (far right) ──────────────────────────────────────────
        _svg_path = get_affilabs_resource("ui/img/sparq_icon.svg")
        _robot_svg = (
            _svg_path.read_text(encoding="utf-8")
            if _svg_path and _svg_path.exists()
            else '<svg width="24" height="24" viewBox="0 0 24 24" fill="none">'
                 '<rect x="5" y="6" width="14" height="12" rx="2" stroke="currentColor" stroke-width="1.25"/>'
                 '<circle cx="9" cy="10" r="1.5" fill="currentColor"/>'
                 '<circle cx="15" cy="10" r="1.5" fill="currentColor"/>'
                 '<path d="M9 14h6" stroke="currentColor" stroke-width="1.25" stroke-linecap="round"/>'
                 '<path d="M3 10v4M21 10v4" stroke="currentColor" stroke-width="1.25" stroke-linecap="round"/></svg>'
        )
        self.spark_toggle_btn = self._icon_btn(
            icon=_svg_icon(_robot_svg, "#FF6B00", "#FFFFFF"),
            tip="Toggle Sparq AI assistant",
            checkable=True,
            style_override=(
                "QPushButton { background: rgba(255,107,0,0.12); border: 1.5px solid rgba(255,107,0,0.50); border-radius: 8px; }"
                "QPushButton:hover { background: rgba(255,107,0,0.20); border-color: rgba(255,107,0,0.75); }"
                "QPushButton:checked { background: #FF6B00; border: 1.5px solid #FF6B00; }"
                "QPushButton:checked:hover { background: #E05F00; border-color: #E05F00; }"
            ),
        )
        self.spark_toggle_btn.toggled.connect(self.main_window._on_spark_toggle)
        self.main_window.spark_toggle_btn = self.spark_toggle_btn
        layout.addWidget(self.spark_toggle_btn)

        # ── Timer button — kept alive off-layout for mixin compatibility ───────
        # The visible timer lives in IconRail (RailTimerPopup). This stub keeps
        # main_window.timer_button valid so TimerMixin calls don't crash.
        try:
            from affilabs.widgets.timer_button import TimerButton
            self.timer_button = TimerButton(parent=self.main_window)
            self.timer_button.set_compact_mode(True)
            self.timer_button.hide()  # not in layout — invisible stub
            self.timer_button.clear_requested.connect(self.main_window._on_clear_manual_timer)
            self.timer_button.restart_requested.connect(self.main_window._on_restart_manual_timer)
            self.main_window.timer_button = self.timer_button
        except Exception as e:
            logger.error(f"TransportBar: TimerButton stub failed (non-fatal): {e}")

        # ── Pause + Record — hidden stubs (buttons live in sidebar controls row) ─
        # main_window.pause_btn / record_btn refs kept for mixin compatibility.
        self.pause_btn = QPushButton(parent=self.main_window)
        self.pause_btn.setCheckable(True)
        self.pause_btn.setEnabled(False)
        self.pause_btn.hide()
        self.pause_btn.clicked.connect(self.main_window._toggle_pause)
        self.main_window.pause_btn = self.pause_btn

        self.record_btn = QPushButton(parent=self.main_window)
        self.record_btn.setCheckable(True)
        self.record_btn.setEnabled(False)
        self.record_btn.hide()
        self.record_btn.clicked.connect(self.main_window._toggle_recording)
        self.main_window.record_btn = self.record_btn

        # ── Hidden compat widgets (used by coordinator / mixin checks) ─────────
        self.recording_indicator = QFrame()
        self.recording_indicator.setVisible(False)
        self.rec_status_dot = QLabel("●")
        self.rec_status_dot.setVisible(False)
        self.main_window.recording_indicator = self.recording_indicator
        self.main_window.rec_status_dot = self.rec_status_dot

        # connecting_label  — stays as an overlay, not in layout
        self.main_window.connecting_label = QLabel("Connecting to hardware...")
        self.main_window.connecting_label.setVisible(False)
        self.main_window.connecting_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_window.connecting_label.setStyleSheet(
            "QLabel {"
            "  color: #1D1D1F; background: rgba(255,255,255,0.97);"
            "  font-size: 18px; font-weight: 700;"
            "  padding: 20px 40px; border: 3px solid #E6B800; border-radius: 14px;"
            "}"
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _icon_btn(
        self,
        icon: QIcon,
        tip: str,
        checkable: bool = False,
        style_override: str = "",
    ) -> QPushButton:
        btn = QPushButton()
        btn.setFixedSize(_BTN_W, _BTN_H)
        btn.setCheckable(checkable)
        btn.setChecked(False)
        btn.setToolTip(tip)
        btn.setIcon(icon)
        btn.setIconSize(QSize(20, 20))
        btn.setStyleSheet(style_override or _BTN_BASE)
        return btn

    @staticmethod
    def _sep() -> QFrame:
        f = QFrame()
        f.setObjectName("sep")
        f.setFrameShape(QFrame.Shape.VLine)
        f.setFixedWidth(1)
        f.setStyleSheet("background: #E5E5EA; margin: 6px 0;")
        return f
