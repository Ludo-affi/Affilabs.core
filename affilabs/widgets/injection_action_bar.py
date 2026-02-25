"""InjectionActionBar — Contact Monitor panel embedded below the cycle queue table.

The panel has a PERMANENT 4-channel binding visualizer (A B C D) always visible:
  ○ Grey   — idle / channel inactive (panel dormant during non-binding cycles)
  ● Yellow — channel expecting injection (Phase 1 "Get Ready")
  ◉ Green  — injection detected, sample in contact (Phase 2 auto-detect)
  ○· Wash  — buffer wash phase (sky-blue dot departing ring)

Three states:

  Idle (default):
    LEDs shown grey. Subtle placeholder text.

  Phase 1 — "Get Ready":
    ┌──────────────────────────────────────────────────┐
    │  [Ready 18s]  Ch A · 100nM   A● B○ C○ D○ [✕]   │
    └──────────────────────────────────────────────────┘
    Action button left, big and prominent.
    Active channels lit yellow.

  Phase 2 — "Inject + Detect":
    ┌──────────────────────────────────────────────────┐
    │  💉 Injecting   A● B● C○ D○        [Done] [✕]   │
    │  ✓ Detected on A  —  Contact: 02:45 remaining   │
    └──────────────────────────────────────────────────┘
    Channels go green as injection detected.
    Contact time countdown if provided.

Public API
----------
show_phase1(label, channels, on_ready, on_cancel)
show_phase2(channels, on_done, on_cancel, contact_time=None)
    contact_time: seconds (int/float) to count down after injection starts
update_channel_detected(channel, detected)
update_status(text)
hide()
"""

from __future__ import annotations

import logging
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)

from PySide6.QtCore import Qt, QRectF, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

_FONT = "-apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif"
_MONO = "'SF Mono', 'Cascadia Code', 'Consolas', monospace"

_GREEN  = "#34C759"
_YELLOW = "#FF9500"
_GREY   = "#C7C7CC"
_TEXT   = "#1D1D1F"
_MUTED  = "#86868B"
_BLUE   = "#007AFF"

_BTN_CANCEL = (
    "QPushButton { background: transparent; border: 1px solid rgba(0,0,0,0.15);"
    " border-radius: 6px; padding: 0 10px; font-size: 11px; font-weight: 500;"
    f" color: {_MUTED}; font-family: {_FONT}; }}"
    " QPushButton:hover { background: rgba(0,0,0,0.06); }"
)
_BTN_READY = (
    "QPushButton { background: #007AFF; border: none; border-radius: 8px;"
    " font-size: 13px; font-weight: 700; color: white;"
    f" font-family: {_FONT}; }}"
    " QPushButton:hover { background: #0051D5; }"
    " QPushButton:pressed { background: #003D99; }"
)
_BTN_DONE = (
    "QPushButton { background: #34C759; border: none; border-radius: 8px;"
    " font-size: 13px; font-weight: 700; color: white;"
    f" font-family: {_FONT}; }}"
    " QPushButton:hover { background: #28A745; }"
)

_ALL_CHANNELS = ("A", "B", "C", "D")


# ── Channel binding state ────────────────────────────────────────────────────

class ChannelState:
    """Constants for the three-phase binding lifecycle per SPR channel."""
    INACTIVE = "inactive"   # grey ring, no dot — channel not part of this cycle
    PENDING  = "pending"    # dot approaching from left — injection in progress
    CONTACT  = "contact"    # dot snapped inside ring — sample in contact with surface
    WASH     = "wash"        # dot departing right — buffer washing sample off


class ChannelBindingWidget(QWidget):
    """Custom-painted ring+dot indicator showing the SPR binding lifecycle.

    States:
      INACTIVE  — open ring, no dot
      PENDING   — open ring, small dot to the LEFT (approaching the surface)
      CONTACT   — filled dot snapped INSIDE the ring (sample bound to ligand)
      WASH      — open ring, small dot to the RIGHT (departing / washing out)
    """

    _RING_R   = 9    # ring radius px
    _DOT_R    = 4    # analyte dot radius px
    _DOT_DIST = 18   # px from ring centre when approaching or departing

    # (ring_color, dot_color) per state
    _PALETTE = {
        ChannelState.INACTIVE: ("#C7C7CC", "#C7C7CC"),
        ChannelState.PENDING:  ("#FF9500", "#FF9500"),
        ChannelState.CONTACT:  ("#34C759", "#34C759"),
        ChannelState.WASH:     ("#86868B", "#5AC8FA"),  # grey ring, sky-blue dot
    }

    def __init__(self, channel: str, parent=None):
        super().__init__(parent)
        self._channel = channel
        self._state   = ChannelState.INACTIVE
        self.setMinimumHeight(36)
        self.setMaximumHeight(44)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)

    def set_state(self, state: str) -> None:
        self._state = state
        self.update()

    @property
    def state(self) -> str:
        return self._state

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w  = self.width()
        h  = self.height()
        cy = h / 2.0
        ring_cx = w / 2.0

        ring_color, dot_color = self._PALETTE.get(
            self._state, self._PALETTE[ChannelState.INACTIVE]
        )

        # Ring
        p.setPen(QPen(QColor(ring_color), 2.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        r = self._RING_R
        p.drawEllipse(QRectF(ring_cx - r, cy - r, r * 2, r * 2))

        # Dot
        dr = self._DOT_R
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(dot_color)))
        if self._state == ChannelState.PENDING:
            dot_x = ring_cx - self._DOT_DIST
            p.drawEllipse(QRectF(dot_x - dr, cy - dr, dr * 2, dr * 2))
        elif self._state == ChannelState.CONTACT:
            p.drawEllipse(QRectF(ring_cx - dr, cy - dr, dr * 2, dr * 2))
        elif self._state == ChannelState.WASH:
            dot_x = ring_cx + self._DOT_DIST
            p.drawEllipse(QRectF(dot_x - dr, cy - dr, dr * 2, dr * 2))
        # INACTIVE: no dot drawn

        p.end()


class InjectionActionBar(QFrame):
    """Compact two-phase injection bar embedded in the sidebar below the queue table."""

    PHASE1_SECONDS = 10   # Wait 10s before monitoring starts (cycle settle time)
    PHASE2_SECONDS = 80   # Monitor for 80s (covers t=10s→90s of the binding cycle)

    # Emitted when a per-channel contact countdown reaches zero.
    # Payload: channel letter (str), e.g. "A"
    channel_countdown_complete = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("InjectionActionBar")
        self.setMaximumHeight(280)
        self.setStyleSheet(
            "QFrame#InjectionActionBar {"
            "  background: #F2F2F7;"
            "  border-radius: 8px;"
            "}"
            "QFrame#InjectionActionBar QLabel {"
            "  background: transparent;"
            "}"
        )

        self._on_ready_cb: Callable | None = None
        self._on_done_cb: Callable | None = None
        self._on_cancel_cb: Callable | None = None

        self._channel_roles: dict[str, str] = {ch: "\u2014" for ch in _ALL_CHANNELS}

        # Per-channel independent contact countdown state
        self._ch_timers: dict[str, QTimer] = {}
        self._ch_remaining: dict[str, int] = {}
        self._ch_timer_labels: dict[str, QLabel] = {}
        for ch in _ALL_CHANNELS:
            t = QTimer(self)
            t.setInterval(1000)
            t.timeout.connect(lambda c=ch: self._ch_tick(c))
            self._ch_timers[ch] = t
            self._ch_remaining[ch] = 0

        self._countdown = 0
        self._contact_countdown: Optional[int] = None  # Phase 2 contact time
        self._window_start: float | None = None
        self._active_channels: set[str] = set()   # All channels being monitored (from cycle)
        self._detected_channels: set[str] = set() # Subset that actually auto-detected
        self._phase1_done = False
        self._first_detection_fired = False  # True once any channel auto-detected
        self._panel_active: bool = False  # Dormant until a binding cycle activates it

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

        self._setup_ui()
        # Starts dormant (greyed out) — activated when a binding cycle begins
        self._apply_dormant_appearance()

    # ── Construction ─────────────────────────────────────────────────────────

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Section header ────────────────────────────────────────────────
        header_row = QFrame()
        header_row.setStyleSheet(
            "background: transparent; border: none;"
            " border-bottom: 1px solid rgba(0,0,0,0.08);"
        )
        header_hlayout = QHBoxLayout(header_row)
        header_hlayout.setContentsMargins(10, 5, 10, 5)
        self._header_lbl = QLabel("CONTACT MONITOR")
        self._header_lbl.setStyleSheet(
            f"font-size: 12px; font-weight: 700; color: {_MUTED};"
            f" font-family: {_FONT}; letter-spacing: 1.4px;"
            f" background: transparent; border: none;"
        )
        self._header_lbl.setMinimumWidth(130)
        header_hlayout.addWidget(self._header_lbl)
        header_hlayout.addStretch()
        outer.addWidget(header_row)

        # ── Vertical channel binding rows — always visible ────────────────
        self._channel_widgets: dict[str, ChannelBindingWidget] = {}
        self._channel_role_labels: dict[str, QLabel] = {}

        channels_container = QFrame()
        channels_container.setStyleSheet("background: transparent; border: none;")
        channels_vlayout = QVBoxLayout(channels_container)
        channels_vlayout.setContentsMargins(0, 0, 0, 0)
        channels_vlayout.setSpacing(0)

        # ── Column headers ────────────────────────────────────────────────
        col_header = QFrame()
        col_header.setStyleSheet(
            "background: rgba(0,0,0,0.03); border: none;"
            " border-bottom: 1px solid rgba(0,0,0,0.08);"
        )
        col_hlayout = QHBoxLayout(col_header)
        col_hlayout.setContentsMargins(10, 4, 10, 4)
        col_hlayout.setSpacing(6)
        _col_style = (
            f"font-size: 10px; font-weight: 700; color: #8E8E93;"
            f" font-family: {_FONT}; letter-spacing: 0.8px;"
            f" border: none; background: transparent;"
        )
        _cell_h = QLabel("CH")
        _cell_h.setFixedWidth(28)
        _cell_h.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
        _cell_h.setStyleSheet(_col_style)
        col_hlayout.addWidget(_cell_h)
        _status_h = QLabel("STATE")
        _status_h.setFixedWidth(72)
        _status_h.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
        _status_h.setStyleSheet(_col_style)
        col_hlayout.addWidget(_status_h)
        _action_h = QLabel("SAMPLE")
        _action_h.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        _action_h.setStyleSheet(_col_style)
        col_hlayout.addWidget(_action_h, 1)
        _time_h = QLabel("TIME")
        _time_h.setFixedWidth(46)
        _time_h.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        _time_h.setStyleSheet(_col_style)
        col_hlayout.addWidget(_time_h)
        channels_vlayout.addWidget(col_header)

        for i, ch in enumerate(_ALL_CHANNELS):
            row_frame = QFrame()
            row_frame.setObjectName(f"ChRow_{ch}")
            border_bottom = (
                "border-bottom: 1px solid rgba(0,0,0,0.06);"
                if i < len(_ALL_CHANNELS) - 1 else ""
            )
            row_frame.setStyleSheet(
                f"QFrame#ChRow_{ch} {{"
                f"  background: transparent;"
                f"  {border_bottom}"
                f"}}"
            )
            row_layout = QHBoxLayout(row_frame)
            row_layout.setContentsMargins(10, 8, 10, 8)
            row_layout.setSpacing(8)

            # Channel letter
            ch_lbl = QLabel(ch)
            ch_lbl.setFixedWidth(20)
            ch_lbl.setAlignment(
                Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
            )
            ch_lbl.setStyleSheet(
                f"font-size: 15px; font-weight: 800; color: #1D1D1F;"
                f" font-family: {_FONT}; letter-spacing: 0.5px;"
                f" border: none; background: transparent;"
            )
            row_layout.addWidget(ch_lbl)

            # Binding ring+dot visualizer
            bw = ChannelBindingWidget(ch)
            bw.setFixedWidth(80)
            row_layout.addWidget(bw)
            self._channel_widgets[ch] = bw

            # Role label (left-aligned) — shows Sample / Reference / Buffer / —
            # Text is set by set_channel_role(); color dims/brightens with state
            role_lbl = QLabel("\u2014")
            role_lbl.setAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            role_lbl.setStyleSheet(
                f"font-size: 12px; font-weight: 600; color: #3A3A3C; font-family: {_FONT};"
                f" border: none; background: transparent;"
            )
            row_layout.addWidget(role_lbl, 1)
            self._channel_role_labels[ch] = role_lbl

            # Per-channel contact countdown label (hidden until detection)
            timer_lbl = QLabel()
            timer_lbl.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            timer_lbl.setStyleSheet(
                f"font-size: 14px; font-weight: 800; color: {_GREEN};"
                f" font-family: {_MONO};"
                f" border: none; background: transparent;"
            )
            timer_lbl.setFixedWidth(52)
            timer_lbl.setVisible(False)
            row_layout.addWidget(timer_lbl)
            self._ch_timer_labels[ch] = timer_lbl

            channels_vlayout.addWidget(row_frame)

        # Legend strip — explains the three symbol states once
        legend = QLabel("\u00b7\u25cb approaching \u00b7\u25c9 contact \u25cb\u00b7 wash")
        legend.setAlignment(Qt.AlignmentFlag.AlignCenter)
        legend.setStyleSheet(
            f"font-size: 11px; color: #AEAEB2; font-family: {_MONO};"
            f" border-top: 1px solid rgba(0,0,0,0.06);"
            f" background: transparent; padding: 4px 0 4px 0;"
        )
        channels_vlayout.addWidget(legend)

        outer.addWidget(channels_container)

        # Divider before active controls
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet("background: rgba(0,0,0,0.08); border: none;")
        outer.addWidget(div)

        # Stacked content: page 0 = idle, page 1 = active
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background: transparent;")
        outer.addWidget(self._stack, 1)

        # ── Page 0: Idle ─────────────────────────────────────────────────
        idle_page = QFrame()
        idle_page.setStyleSheet("background: transparent; border: none;")
        idle_layout = QVBoxLayout(idle_page)
        idle_layout.setContentsMargins(12, 6, 12, 6)
        idle_layout.addStretch()

        self._idle_lbl = QLabel("No binding cycle active")
        self._idle_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._idle_lbl.setWordWrap(True)
        self._idle_lbl.setStyleSheet(
            f"font-size: 12px; color: {_MUTED}; font-family: {_FONT};"
        )
        idle_layout.addWidget(self._idle_lbl)

        self._idle_sub = QLabel()
        self._idle_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._idle_sub.setWordWrap(True)
        self._idle_sub.setStyleSheet(
            f"font-size: 12px; color: #AEAEB2; font-family: {_FONT};"
        )
        self._idle_sub.setVisible(False)
        idle_layout.addWidget(self._idle_sub)

        idle_layout.addStretch()
        self._stack.addWidget(idle_page)   # index 0

        # ── Page 1: Active ────────────────────────────────────────────────
        active_page = QFrame()
        active_page.setStyleSheet("background: transparent; border: none;")
        active_layout = QVBoxLayout(active_page)
        active_layout.setContentsMargins(10, 4, 10, 4)
        active_layout.setSpacing(2)

        # Single compact label — shows inline countdown during phase 1,
        # plain status text during phase 2.  No badge, no buttons.
        self._label = QLabel()
        self._label.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: {_TEXT}; font-family: {_FONT};"
        )
        self._label.setWordWrap(True)
        active_layout.addWidget(self._label)

        # Phase 1 badge kept as hidden attribute for backward compat but never shown
        self._phase1_badge = self._label   # alias — tick updates _label directly
        self._cancel_btn = None             # no cancel button

        # Row 2: status + contact countdown (Phase 2 only)
        self._row2_widget = QFrame()
        self._row2_widget.setStyleSheet("background: transparent; border: none;")
        row2 = QHBoxLayout(self._row2_widget)
        row2.setContentsMargins(0, 0, 0, 0)
        row2.setSpacing(8)

        self._status_label = QLabel()
        self._status_label.setStyleSheet(
            f"font-size: 13px; color: {_GREEN}; font-family: {_FONT};"
        )
        row2.addWidget(self._status_label, 1)

        self._timer_label = QLabel()
        self._timer_label.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {_BLUE}; font-family: {_MONO};"
        )
        row2.addWidget(self._timer_label)

        active_layout.addWidget(self._row2_widget)
        self._row2_widget.setVisible(False)

        self._stack.addWidget(active_page)   # index 1

    # ── Public API ────────────────────────────────────────────────────────────

    def set_panel_active(self, active: bool) -> None:
        """Activate or deactivate the Contact Monitor panel.

        When *active* is True (binding cycle running), the panel shows its
        normal blue/green appearance and responds to injections.

        When *active* is False (non-binding cycle, e.g. Baseline, Wash,
        Regen, or no cycle at all), the panel is greyed out / dormant —
        all elements muted, timers stopped, interactions disabled.

        Call this from the cycle coordinator when a cycle starts/stops.
        """
        self._panel_active = active
        if active:
            self._apply_active_appearance()
        else:
            # Stop any running timers and reset state
            self._timer.stop()
            self._active_channels.clear()
            self._detected_channels.clear()
            self._first_detection_fired = False
            for ch in _ALL_CHANNELS:
                self._stop_channel_countdown(ch)
            self._reset_all_leds()
            self._stack.setCurrentIndex(0)
            self._apply_dormant_appearance()

    @property
    def panel_active(self) -> bool:
        """Whether the panel is currently active (binding cycle in progress)."""
        return bool(self._panel_active)

    def show_phase1(
        self,
        label: str,
        channels: str,
        on_ready: Callable,
        on_cancel: Callable,
        contact_time: Optional[float] = None,
    ) -> None:
        """Show Phase 1: Get Ready — tell user exactly when/where/how long."""
        # Auto-activate panel when an injection phase begins
        if not self._panel_active:
            self.set_panel_active(True)
        self._on_ready_cb = on_ready
        self._on_cancel_cb = on_cancel
        self._phase1_done = False
        self._contact_countdown = int(contact_time) if contact_time else None
        self._active_channels = set(channels.upper())

        # Build instruction line inline — countdown shown as trailing "· Ns"
        ch_str = ", ".join(sorted(self._active_channels)) if self._active_channels else channels.upper()
        self._phase1_ch_str = ch_str          # saved for tick updates
        self._phase1_hold_str = ""
        if self._contact_countdown:
            m, s = divmod(self._contact_countdown, 60)
            self._phase1_hold_str = f"  ·  Hold {m}m {s:02d}s" if m else f"  ·  Hold {s}s"
        self._label.setText(
            f"Inject into {ch_str}{self._phase1_hold_str}  ·  monitoring in {self.PHASE1_SECONDS}s"
        )

        self._row2_widget.setVisible(False)

        self._set_channel_colors_for_phase1()

        self._countdown = self.PHASE1_SECONDS
        self._timer.start(1000)
        self._stack.setCurrentIndex(1)

    def show_phase2(
        self,
        channels: str,
        on_done: Callable,
        on_cancel: Callable,
        contact_time: Optional[float] = None,
    ) -> None:
        """Switch to Phase 2: injection monitoring.

        Args:
            channels: Uppercase string of channels to monitor, e.g. "ABCD"
            on_done: Called when Done clicked or timeout
            on_cancel: Called when Cancel clicked
            contact_time: Contact time in seconds to count down (optional)
        """
        # Auto-activate panel when an injection phase begins
        if not self._panel_active:
            self.set_panel_active(True)
        self._on_done_cb = on_done
        self._on_cancel_cb = on_cancel
        self._phase1_done = True
        self._first_detection_fired = False
        self._active_channels = set(channels.upper())
        self._detected_channels = set()  # Reset — populated as channels auto-detect

        self._timer.stop()
        self._window_start = time.time()
        self._contact_countdown = int(contact_time) if contact_time else None

        self._set_channel_colors_for_phase1()
        self._set_bar_idle_appearance()

        ch_str = ", ".join(sorted(self._active_channels)) if self._active_channels else "?"
        self._label.setText(f"Monitoring {ch_str} for injection…")

        # Row 2: show monitoring state — contact countdown starts only after
        # first detection fires via update_channel_detected().
        self._status_label.setText("Monitoring…")
        self._status_label.setStyleSheet(
            f"font-size: 13px; color: {_MUTED}; font-family: {_FONT};"
        )
        self._timer_label.setText("")
        self._row2_widget.setVisible(True)

        self._countdown = self.PHASE2_SECONDS  # detection window only; contact time starts at detection
        self._timer.start(1000)

    def update_channel_detected(self, channel: str, detected: bool) -> None:
        """Light up (green) or revert (yellow) a channel LED.

        On the first detection in Phase 2, restarts the contact time countdown
        from 0 so the full configured contact window is measured from the
        moment of injection, not from when the phase began.
        """
        ch = channel.upper()
        bw = self._channel_widgets.get(ch)
        if bw:
            if detected:
                bw.set_state(ChannelState.CONTACT)
                self._set_role_label_color(ch, _GREEN)
                self._detected_channels.add(ch)  # Track which channels actually detected
                # Start per-channel countdown if contact_time is configured
                if self._contact_countdown and self._ch_remaining.get(ch, 0) <= 0:
                    self._start_channel_countdown(ch, self._contact_countdown)
            elif ch in self._active_channels:
                bw.set_state(ChannelState.PENDING)
                self._set_role_label_color(ch, _YELLOW)
            else:
                bw.set_state(ChannelState.INACTIVE)
                self._set_role_label_color(ch, _MUTED)

        # First detection in Phase 2
        # Update ACTION column text for this channel
        if detected:
            self._set_channel_action(ch, "Contact")
        elif ch in self._active_channels:
            self._set_channel_action(ch, "Waiting")

        if detected and self._phase1_done and not self._first_detection_fired:
            self._first_detection_fired = True
            if self._contact_countdown is not None:
                # Restart contact countdown from the full duration
                self._countdown = self._contact_countdown
                self._window_start = time.time()
                m, s = divmod(self._contact_countdown, 60)
                self._timer_label.setText(f"{m:02d}:{s:02d}")
                self._timer_label.setStyleSheet(
                    f"font-size: 13px; font-weight: 700; color: {_GREEN};"
                    f" font-family: {_MONO};"
                )
            else:
                # No contact time — auto-complete after a brief visual confirmation delay
                self._status_label.setText("✓ Injection detected — continuing…")
                self._status_label.setStyleSheet(
                    f"font-size: 13px; color: {_GREEN}; font-family: {_FONT};"
                )
                QTimer.singleShot(1500, self._fire_done)

    def set_channel_wash(self, channel: str) -> None:
        """Transition a channel to the WASH state (dot departing right of ring).

        Call this when wash injection is detected for a channel.
        Stops that channel's overrun timer. When all active channels have been
        washed, stops the global bar timer and fires done.
        """
        ch = channel.upper()
        bw = self._channel_widgets.get(ch)
        if bw:
            bw.set_state(ChannelState.WASH)
            self._set_role_label_color(ch, "#5AC8FA")
        self._set_channel_action(ch, "Wash")
        self._stop_channel_countdown(ch)

        # Check if all *detected* channels are now in WASH state.
        # Use _detected_channels (not _active_channels) so that channels which
        # never auto-detected (e.g. D when only A/B/C were used) don't block completion.
        wash_set = self._detected_channels if self._detected_channels else self._active_channels
        all_washed = bool(wash_set) and all(
            self._channel_widgets.get(c) is not None
            and self._channel_widgets[c].state == ChannelState.WASH
            for c in wash_set
        )
        if all_washed:
            self._timer.stop()
            self._clear_overlay_injection()
            self._set_bar_idle_appearance()
            QTimer.singleShot(800, self._fire_done)

    def set_upcoming(self, label: str, channels: str) -> None:
        """Pre-announce an upcoming injection in the idle pane.

        Call this as soon as a binding cycle starts so the user can see
        what will be injected before the Phase 1 countdown begins.

        Args:
            label: Succinct injection description, e.g. "Ch A · 100nM · 300s"
            channels: Active channel string, e.g. "A" or "ABCD"
        """
        # Auto-activate panel — upcoming injection means binding cycle
        if not self._panel_active:
            self.set_panel_active(True)
        self._idle_lbl.setText("Next injection")
        self._idle_lbl.setStyleSheet(
            f"font-size: 11px; font-weight: 600; color: {_MUTED}; font-family: {_FONT};"
            " text-transform: uppercase; letter-spacing: 0.5px;"
        )
        self._idle_sub.setText(label)
        self._idle_sub.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: {_TEXT}; font-family: {_FONT};"
        )
        self._idle_sub.setVisible(True)
        # Pre-light the channels yellow so user sees which channels are active
        active = set(channels.upper())
        for ch, bw in self._channel_widgets.items():
            if ch in active:
                bw.set_state(ChannelState.PENDING)
                self._set_role_label_color(ch, _YELLOW)
            else:
                bw.set_state(ChannelState.INACTIVE)
                self._set_role_label_color(ch, _MUTED)

    def update_status(self, text: str) -> None:
        """Update the Phase 2 status line."""
        self._status_label.setText(text)
        self._status_label.setStyleSheet(
            f"font-size: 13px; color: {_GREEN}; font-family: {_FONT};"
        )

    def set_channel_role(self, channel: str, role: str) -> None:
        """Set the sample role label for a channel.

        Call this before show_phase2() to annotate each channel with its
        injection role. Role is displayed persistently until hide() is called.

        Args:
            channel: 'A', 'B', 'C', or 'D'
            role:    e.g. 'Sample', 'Reference', 'Buffer', or '\u2014'
        """
        ch = channel.upper()
        self._channel_roles[ch] = role
        lbl = self._channel_role_labels.get(ch)
        if lbl:
            lbl.setText(role)

    def _set_channel_action(self, channel: str, action: str) -> None:
        """Update the ACTION column text for a channel.

        Shows contextual state: 'Waiting', 'Contact', 'Wash', or '\u2014'.
        """
        ch = channel.upper()
        lbl = self._channel_role_labels.get(ch)
        if lbl:
            lbl.setText(action)

    def hide(self) -> None:
        """Return to idle state and clear upcoming label."""
        self._timer.stop()
        self._active_channels.clear()
        self._detected_channels.clear()
        self._first_detection_fired = False
        # Reset roles and per-channel timers
        for ch in _ALL_CHANNELS:
            self._channel_roles[ch] = "\u2014"
            lbl = self._channel_role_labels.get(ch)
            if lbl:
                lbl.setText("\u2014")
            self._stop_channel_countdown(ch)
        self._reset_all_leds()
        self._idle_sub.setVisible(False)
        self._stack.setCurrentIndex(0)
        # Return to dormant — panel greys out until next binding cycle
        self._panel_active = False
        self._apply_dormant_appearance()

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _blink_ready_button(self) -> None:
        """No-op — ready button removed (non-interactive phase 1)."""

    def _set_role_label_color(self, ch: str, color: str) -> None:
        lbl = self._channel_role_labels.get(ch)
        if lbl:
            lbl.setStyleSheet(
                f"font-size: 12px; font-weight: 600; color: {color}; font-family: {_FONT};"
                f" border: none; background: transparent;"
            )

    def _set_channel_colors_for_phase1(self) -> None:
        for ch, bw in self._channel_widgets.items():
            if ch in self._active_channels:
                bw.set_state(ChannelState.PENDING)
                self._set_role_label_color(ch, _YELLOW)
                self._set_channel_action(ch, "Waiting")
            else:
                bw.set_state(ChannelState.INACTIVE)
                self._set_role_label_color(ch, _MUTED)
                self._set_channel_action(ch, "\u2014")

    def _reset_all_leds(self) -> None:
        for ch, bw in self._channel_widgets.items():
            bw.set_state(ChannelState.INACTIVE)
            self._set_role_label_color(ch, _MUTED)
            self._stop_channel_countdown(ch)

    # ── Per-channel countdown logic ───────────────────────────────────────────

    def _start_channel_countdown(self, ch: str, total_seconds: int) -> None:
        """Begin an independent contact-time countdown for one channel."""
        self._ch_remaining[ch] = total_seconds
        lbl = self._ch_timer_labels.get(ch)
        if lbl:
            lbl.setText(self._fmt_time(total_seconds))
            lbl.setStyleSheet(
                f"font-size: 14px; font-weight: 800; color: {_GREEN};"
                f" font-family: {_MONO};"
                f" border: none; background: transparent;"
            )
            lbl.setVisible(True)
        self._ch_timers[ch].start()

    def _stop_channel_countdown(self, ch: str) -> None:
        """Stop and hide a channel's countdown."""
        timer = self._ch_timers.get(ch)
        if timer:
            timer.stop()
        self._ch_remaining[ch] = 0
        lbl = self._ch_timer_labels.get(ch)
        if lbl:
            lbl.setVisible(False)
            lbl.setText("")

    _OVERRUN_CAP_S: int = 120  # Stop timer after 120 s past contact end if no wash

    def _ch_tick(self, ch: str) -> None:
        """Per-channel 1-second tick.

        Counts down to 0:00, emits channel_countdown_complete, then continues
        into negative (overrun) until wash is detected on this channel.
        Stops automatically at -_OVERRUN_CAP_S if wash is never detected.
        """
        self._ch_remaining[ch] -= 1
        remaining = self._ch_remaining[ch]   # may be negative (overrun)
        lbl = self._ch_timer_labels.get(ch)

        if remaining == 0:
            # Contact time just expired — signal upstream and cue the user to wash
            self.channel_countdown_complete.emit(ch)
            self._set_channel_action(ch, "Wash now!")
            self._set_role_label_color(ch, "#FF3B30")

        if remaining <= -self._OVERRUN_CAP_S:
            # Overrun cap hit — wash never came; stop and flag
            self._stop_channel_countdown(ch)
            if lbl:
                lbl.setText("–")
            self._set_channel_action(ch, "No wash detected")
            self._set_role_label_color(ch, "#FF3B30")
            logger.warning(f"Channel {ch}: overrun cap hit (+{self._OVERRUN_CAP_S}s) — wash not detected")
            return

        if lbl:
            lbl.setText(self._fmt_time(remaining))
            if remaining > 10:
                color = _GREEN
            elif remaining > 0:
                color = _YELLOW          # last 10 seconds — amber warning
            elif remaining == 0:
                color = _YELLOW          # still amber at the boundary
            else:
                color = "#FF3B30"        # red while overrunning (wash not yet done)
            lbl.setStyleSheet(
                f"font-size: 14px; font-weight: 800; color: {color};"
                f" font-family: {_MONO};"
                f" border: none; background: transparent;"
            )

    def _auto_wash_channel(self, ch: str) -> None:
        """No longer used — wash transitions only happen via set_channel_wash()."""

    @staticmethod
    def _fmt_time(seconds: int) -> str:
        """Format seconds as M:SS, with a leading minus sign when overrunning."""
        if seconds < 0:
            m, s = divmod(-seconds, 60)
            return f"-{m}:{s:02d}"
        m, s = divmod(seconds, 60)
        return f"{m}:{s:02d}"

    def _set_bar_detected_appearance(self) -> None:
        """Keep neutral appearance after injection detected (no green overlay)."""
        # Intentionally no visual change — detection state is shown per-channel
        # via the ring/dot indicator and per-channel countdown timers.
        pass

    def _set_bar_idle_appearance(self) -> None:
        """Restore default neutral idle appearance."""
        self.setStyleSheet(
            "QFrame#InjectionActionBar {"
            "  background: #F2F2F7;"
            "  border-radius: 8px;"
            "}"
            "QFrame#InjectionActionBar QLabel {"
            "  background: transparent;"
            "}"
        )

    def _apply_dormant_appearance(self) -> None:
        """Grey out the entire panel — used when no binding cycle is active.

        Mutes the frame border/bg, header, channel rows, legend, and idle text
        to signal that the Contact Monitor is inactive.

        Visual distinction from active: dashed border, lighter text (#C7C7CC
        vs #86868B), no blue tint.  User can tell at a glance that the panel
        is not listening for injections.
        """
        self.setStyleSheet(
            "QFrame#InjectionActionBar {"
            "  background: #F2F2F7;"
            "  border: 1px dashed #C7C7CC;"
            "  border-radius: 8px;"
            "}"
            "QFrame#InjectionActionBar QLabel {"
            "  background: transparent;"
            "}"
        )
        # Also grey out the parent InjectionZone frame so the border turns neutral
        _parent = self.parentWidget()
        if _parent and _parent.objectName() == "InjectionZone":
            _parent.setStyleSheet(
                "QFrame#InjectionZone {"
                "  background: #F2F2F7;"
                "  border: 1px dashed #C7C7CC;"
                "  border-radius: 8px;"
                "}"
            )
        # Dim header — lighter than active (#C7C7CC vs #86868B)
        if hasattr(self, '_header_lbl'):
            self._header_lbl.setStyleSheet(
                f"font-size: 12px; font-weight: 700; color: #C7C7CC;"
                f" font-family: {_FONT}; letter-spacing: 1.4px;"
                f" background: transparent; border: none;"
            )
        # Dim idle text
        if hasattr(self, '_idle_lbl'):
            self._idle_lbl.setText("No binding cycle active")
            self._idle_lbl.setStyleSheet(
                f"font-size: 12px; color: #C7C7CC; font-family: {_FONT};"
            )
        # Grey out all channel widgets and role labels
        for ch in _ALL_CHANNELS:
            bw = self._channel_widgets.get(ch)
            if bw:
                bw.set_state(ChannelState.INACTIVE)
            lbl = self._channel_role_labels.get(ch)
            if lbl:
                lbl.setStyleSheet(
                    f"font-size: 12px; font-weight: 600; color: #C7C7CC; font-family: {_FONT};"
                    f" border: none; background: transparent;"
                )

    def _apply_active_appearance(self) -> None:
        """Restore the panel from dormant to its normal active state.

        Visual distinction from dormant: solid blue-tinted border instead of
        dashed grey.  Signals that the panel is alive and listening for
        injection events.
        """
        # Restore parent InjectionZone frame — subtle blue border = "listening"
        _parent = self.parentWidget()
        if _parent and _parent.objectName() == "InjectionZone":
            _parent.setStyleSheet(
                "QFrame#InjectionZone {"
                "  background: #F8F8FA;"
                "  border: 1.5px solid rgba(0, 122, 255, 0.20);"
                "  border-radius: 8px;"
                "}"
            )
        # Bar frame — matching subtle blue border
        self.setStyleSheet(
            "QFrame#InjectionActionBar {"
            "  background: #F8F8FA;"
            "  border: 1.5px solid rgba(0, 122, 255, 0.20);"
            "  border-radius: 8px;"
            "}"
            "QFrame#InjectionActionBar QLabel {"
            "  background: transparent;"
            "}"
        )
        # Restore header to normal muted color (darker than dormant's #C7C7CC)
        if hasattr(self, '_header_lbl'):
            self._header_lbl.setStyleSheet(
                f"font-size: 12px; font-weight: 700; color: {_MUTED};"
                f" font-family: {_FONT}; letter-spacing: 1.4px;"
                f" background: transparent; border: none;"
            )
        # Restore idle label
        if hasattr(self, '_idle_lbl'):
            self._idle_lbl.setText("Waiting for injection…")
            self._idle_lbl.setStyleSheet(
                f"font-size: 12px; color: {_MUTED}; font-family: {_FONT};"
            )
        # Restore channel labels to normal muted
        for ch in _ALL_CHANNELS:
            self._set_role_label_color(ch, _MUTED)

    # ── Timer tick ────────────────────────────────────────────────────────────

    def _tick(self) -> None:
        self._countdown -= 1

        if not self._phase1_done:
            # Phase 1: count down to auto-ready (non-interactive)
            if self._countdown <= 0:
                self._timer.stop()
                self._fire_ready()
            else:
                # Update inline countdown in label text
                ch_str = getattr(self, '_phase1_ch_str', '?')
                hold_str = getattr(self, '_phase1_hold_str', '')
                self._label.setText(f"Inject into {ch_str}{hold_str}  ·  monitoring in {self._countdown}s")
        else:
            # Phase 2: contact time countdown or elapsed
            if self._contact_countdown is not None:
                if self._first_detection_fired:
                    # Contact time running from injection — count down through 0 and into
                    # negative (overrun) until wash is detected externally.
                    # Timer keeps running; _fire_done() is NOT called here.
                    remaining = self._countdown   # may go negative
                    self._sync_overlay_countdown(max(0, remaining))
                    if remaining <= 0:
                        # Overrun — show negative time in red
                        color = "#FF3B30"
                        self._clear_overlay_injection()
                    elif remaining <= 10:
                        color = _YELLOW
                    else:
                        color = _GREEN
                    self._timer_label.setText(self._fmt_time(remaining))
                    self._timer_label.setStyleSheet(
                        f"font-size: 11px; font-weight: 700; color: {color};"
                        f" font-family: {_MONO};"
                    )
                else:
                    # Waiting for injection — show countdown to end of detection window
                    self._countdown += 1  # undo top decrement; contact time only ticks after detection
                    if self._window_start is not None:
                        waiting = int(time.time() - self._window_start)
                        remaining_detect = max(0, self.PHASE2_SECONDS - waiting)
                        m, s = divmod(remaining_detect, 60)
                        if remaining_detect <= 10:
                            detect_color = "#FF3B30"   # red — urgent
                        elif remaining_detect <= 20:
                            detect_color = _YELLOW     # amber — warning
                        else:
                            detect_color = _MUTED      # grey — normal
                        self._timer_label.setText(f"{m:02d}:{s:02d}")
                        self._timer_label.setStyleSheet(
                            f"font-size: 11px; font-weight: 700; color: {detect_color};"
                            f" font-family: {_MONO};"
                        )
                        self._status_label.setText(
                            f"Inject within {remaining_detect}s…" if remaining_detect > 0
                            else "Window closing…"
                        )
                        # Fallback: if waited beyond PHASE2_SECONDS without detection, fire done
                        if waiting >= self.PHASE2_SECONDS:
                            self._timer.stop()
                            self._fire_done()
            else:
                # Generic elapsed timer (no contact_time configured)
                if self._window_start is not None:
                    elapsed = int(time.time() - self._window_start)
                    m, s = divmod(elapsed, 60)
                    self._timer_label.setText(f"{m:02d}:{s:02d}")

                if self._countdown <= 0:
                    self._timer.stop()
                    self._fire_done()

    # ── Overlay sync ──────────────────────────────────────────────────────────

    def _get_cycle_overlay(self):
        """Walk parent chain to find CycleStatusOverlay on the Active Cycle graph."""
        try:
            w = self.window()
            graph = getattr(w, 'cycle_of_interest_graph', None)
            if graph is None:
                mw = getattr(w, 'main_window', None)
                graph = getattr(mw, 'cycle_of_interest_graph', None)
            return getattr(graph, 'cycle_status_overlay', None)
        except Exception:
            return None

    def _sync_overlay_countdown(self, remaining: float) -> None:
        # Disabled — cycle overlay shows cycle countdown independently;
        # contact time is shown per-channel in the Contact Monitor panel.
        pass

    def _clear_overlay_injection(self) -> None:
        # Disabled — cycle overlay no longer hijacked by injection state.
        pass

    # ── Button handlers ───────────────────────────────────────────────────────

    def _on_cancel(self) -> None:
        self._timer.stop()
        self._active_channels.clear()
        self._first_detection_fired = False
        # Stop all per-channel timers
        for ch in _ALL_CHANNELS:
            self._stop_channel_countdown(ch)
        self._reset_all_leds()
        self._clear_overlay_injection()
        self._stack.setCurrentIndex(0)
        # Return to dormant
        self._panel_active = False
        self._apply_dormant_appearance()
        if self._on_cancel_cb:
            self._on_cancel_cb()

    def _fire_ready(self) -> None:
        if self._phase1_done:
            return
        self._phase1_done = True
        self._timer.stop()
        cb = self._on_ready_cb
        if cb:
            cb()

    def _fire_done(self) -> None:
        self._timer.stop()
        # Stop all per-channel timers
        for ch in _ALL_CHANNELS:
            self._stop_channel_countdown(ch)
        self._active_channels.clear()
        self._detected_channels.clear()
        self._first_detection_fired = False
        self._reset_all_leds()
        self._stack.setCurrentIndex(0)
        # Return to dormant
        self._panel_active = False
        self._apply_dormant_appearance()
        cb = self._on_done_cb
        if cb:
            cb()

    def show_injection_missed(self) -> None:
        """Show a persistent 'injection not detected' message in the bar.

        Called by the coordinator when the detection dialog times out with zero
        detections. Keeps the bar visible with a warning rather than silently
        dismissing it, so the user knows to add flags manually in Edits.
        """
        self._timer.stop()
        for ch in _ALL_CHANNELS:
            self._stop_channel_countdown(ch)
        self._reset_all_leds()
        # Stay visible with an explanatory message — user must dismiss
        self._label.setText("Injection not detected")
        self._status_label.setText("Add flags manually in Edits tab")
        self._status_label.setStyleSheet(
            f"font-size: 11px; color: #FF9500; font-family: {_FONT};"
        )
        self._timer_label.setText("")
        self._row2_widget.setVisible(True)
        self._stack.setCurrentIndex(1)  # show monitoring page
        # Auto-dismiss after 8s so the bar doesn't stay forever
        from PySide6.QtCore import QTimer as _QTimer
        _QTimer.singleShot(8000, lambda: self.set_panel_active(False))

    def show_mislabel_warning(self, detected_channels: str, expected_channels: str) -> None:
        """Flash an orange warning when injection detected on unexpected channels.

        Args:
            detected_channels: e.g. "C, D"
            expected_channels: e.g. "A, B"
        """
        self._status_label.setText(
            f"⚠ Detected on {detected_channels} — expected {expected_channels}"
        )
        self._status_label.setStyleSheet(
            f"font-size: 11px; color: #FF9500; font-weight: 600; font-family: {_FONT};"
        )
