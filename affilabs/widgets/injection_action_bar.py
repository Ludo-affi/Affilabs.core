"""InjectionActionBar — Manual Injection Assistant panel embedded below the cycle queue table.

The panel has a PERMANENT 4-channel binding visualizer (A B C D) always visible:
  ○ Grey   — idle / channel inactive (panel dormant during non-binding cycles)
  ● Green  — sensor ready, waiting for injection
  ◉ Orange — injection detected, sample in contact (spinning dashed ring)
  ○· Wash  — buffer wash phase (sky-blue dot departing ring)

Two states:

  Idle (default):
    LEDs shown grey. Subtle placeholder text.

  Monitoring:
    ┌──────────────────────────────────────────────────┐
    │  Sensor Ready — Inject your sample               │
    │  ✓ Detected on A  —  Contact: 02:45 remaining   │
    └──────────────────────────────────────────────────┘
    Channels go green as injection detected.
    Per-channel contact time countdown shown in TIME column.

Public API
----------
show_monitoring(channels, on_done, on_cancel, contact_time=None)
    Immediately enter monitoring state — no phase 1 countdown.
    contact_time: seconds (int/float) to count down per channel after detection
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

from affilabs.ui_styles import FontScale as _FS

_FONT = "-apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif"
_MONO = "'SF Mono', 'Cascadia Code', 'Consolas', monospace"

_GREEN  = "#34C759"
_BINDING = "#AF52DE"   # Purple — used for "Binding" state labels / dot
_GREY   = "#C7C7CC"
_TEXT   = "#1D1D1F"
_MUTED  = "#86868B"
_BLUE   = "#007AFF"

# Timer urgency colours — must match CycleStatusOverlay contact-time scheme
_TIMER_OK   = "#34C759"   # green  — comfortable (>30 s)
_TIMER_WARN = "#FF9500"   # orange — warning (≤30 s)
_TIMER_CRIT = "#FF3B30"   # red    — critical (≤10 s) / overrun

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
    """Colored circle badge with the channel letter inside.

    The circle color communicates state directly:
      INACTIVE  — light grey circle, muted letter
      PENDING   — amber ring (pulsing feel), dark letter
      CONTACT   — solid green circle, white letter
      WASH      — sky-blue outlined circle, dark letter
    """

    _BADGE_R = 13  # circle radius px — compact to fit row height

    # (bg_color, border_color, text_color) per state
    # Fill is solid/saturated so the channel letter is always legible
    _PALETTE = {
        ChannelState.INACTIVE: ("#D1D1D6", "#C7C7CC", "#FFFFFF"),   # mid-grey fill, white letter
        ChannelState.PENDING:  ("#34C759", "#28A745", "#FFFFFF"),   # solid green, white letter
        ChannelState.CONTACT:  ("#AF52DE", "#9B3DC8", "#FFFFFF"),   # solid purple, white letter
        ChannelState.WASH:     ("#5AC8FA", "#32ADE6", "#FFFFFF"),   # solid sky-blue, white letter
    }

    # Shared animation timer for CONTACT spinning dash (class-level, started on demand)
    _anim_timer: QTimer | None = None
    _anim_angle: float = 0.0
    _anim_instances: set = set()  # ChannelBindingWidgets currently in CONTACT

    @classmethod
    def _ensure_anim_timer(cls) -> None:
        if cls._anim_timer is None:
            cls._anim_timer = QTimer()
            cls._anim_timer.setInterval(40)  # ~25 fps
            cls._anim_timer.timeout.connect(cls._anim_tick)

    @classmethod
    def _anim_tick(cls) -> None:
        cls._anim_angle = (cls._anim_angle + 4.0) % 360.0
        for w in list(cls._anim_instances):
            w.update()

    # Emitted when user manually overrides the state via right-click
    state_override_requested = Signal(str, str)  # (channel, new_state)

    def __init__(self, channel: str, parent=None):
        super().__init__(parent)
        self._channel = channel
        self._state   = ChannelState.INACTIVE
        self.setFixedSize(32, 32)   # compact — fits a 44px row without crowding
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_state_menu)
        self._ensure_anim_timer()

    def set_state(self, state: str) -> None:
        old = self._state
        self._state = state
        # Manage spinning-dash animation membership
        if state == ChannelState.CONTACT:
            self._anim_instances.add(self)
            if not self._anim_timer.isActive():
                self._anim_timer.start()
        elif old == ChannelState.CONTACT:
            self._anim_instances.discard(self)
            if not self._anim_instances and self._anim_timer.isActive():
                self._anim_timer.stop()
        self.update()

    @property
    def state(self) -> str:
        return self._state

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        cx = w / 2.0
        cy = h / 2.0
        r = self._BADGE_R

        bg_color, border_color, text_color = self._PALETTE.get(
            self._state, self._PALETTE[ChannelState.INACTIVE]
        )

        # Circle fill
        p.setPen(QPen(QColor(border_color), 2.0))
        p.setBrush(QBrush(QColor(bg_color)))
        p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

        # Spinning dashed orbit ring for CONTACT state (outside the filled circle)
        if self._state == ChannelState.CONTACT:
            dash_pen = QPen(QColor("#9B3DC8"), 2.0)
            dash_pen.setStyle(Qt.PenStyle.CustomDashLine)
            dash_pen.setDashPattern([4, 3])
            dash_pen.setDashOffset(-self._anim_angle / 10.0)
            p.setPen(dash_pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            orbit_r = r + 4
            p.drawEllipse(QRectF(cx - orbit_r, cy - orbit_r, orbit_r * 2, orbit_r * 2))

        # Channel letter centered inside — always white on solid fill
        from PySide6.QtGui import QFont
        font = QFont("SF Pro Text, Segoe UI, system-ui, sans-serif")
        font.setPixelSize(12)
        font.setWeight(QFont.Weight.Bold)
        p.setFont(font)
        p.setPen(QColor(text_color))
        p.drawText(QRectF(cx - r, cy - r, r * 2, r * 2),
                   Qt.AlignmentFlag.AlignCenter, self._channel)

        p.end()

    def _show_state_menu(self, pos) -> None:
        """Right-click menu — lets user manually correct the detected channel state."""
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #FFFFFF; border: 1px solid #D1D1D6; border-radius: 8px; "
            "        padding: 4px 0; font-size: 13px; }"
            "QMenu::item { padding: 6px 16px; color: #1D1D1F; }"
            "QMenu::item:selected { background: #F0F0F5; border-radius: 4px; }"
            "QMenu::item:disabled { color: #AEAEB2; }"
            "QMenu::separator { height: 1px; background: #E5E5EA; margin: 4px 8px; }"
        )

        title = menu.addAction(f"Channel {self._channel} — Override Status")
        title.setEnabled(False)
        menu.addSeparator()

        _ITEMS = [
            (ChannelState.PENDING,  "🟢  Waiting (ready to inject)"),
            (ChannelState.CONTACT,  "🟣  In Contact (injected)"),
            (ChannelState.WASH,     "🔵  Wash"),
            (ChannelState.INACTIVE, "⚫  Inactive"),
        ]
        for state, label in _ITEMS:
            act = menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(state == self._state)
            act.setData(state)

        chosen = menu.exec(self.mapToGlobal(pos))
        if chosen and chosen.data():
            self.state_override_requested.emit(self._channel, chosen.data())


class InjectionActionBar(QFrame):
    """Manual Injection Assistant panel embedded in the sidebar below the queue table."""

    # Emitted when a per-channel contact countdown reaches zero.
    # Payload: channel letter (str), e.g. "A"
    channel_countdown_complete = Signal(str)

    # Emitted when user manually overrides a channel state via right-click.
    # Payload: (channel: str, new_state: str) — coordinator should sync its internal state.
    channel_state_override = Signal(str, str)

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

        self._on_done_cb: Callable | None = None
        self._on_cancel_cb: Callable | None = None

        self._channel_roles: dict[str, str] = {ch: "\u2014" for ch in _ALL_CHANNELS}

        # Per-channel independent contact countdown state
        self._ch_timers: dict[str, QTimer] = {}
        self._ch_remaining: dict[str, int] = {}
        self._ch_timer_labels: dict[str, QLabel] = {}
        self._ch_conc_labels: dict[str, QLabel] = {}
        for ch in _ALL_CHANNELS:
            t = QTimer(self)
            t.setInterval(1000)
            t.timeout.connect(lambda c=ch: self._ch_tick(c))
            self._ch_timers[ch] = t
            self._ch_remaining[ch] = 0

        self._contact_countdown: Optional[int] = None  # Contact time per channel after detection
        self._window_start: float | None = None
        self._active_channels: set[str] = set()   # All channels being monitored (from cycle)
        self._detected_channels: set[str] = set() # Subset that actually auto-detected
        self._first_detection_fired = False  # True once any channel auto-detected
        self._panel_active: bool = False  # Dormant until a binding cycle activates it
        self._buffer_mgr = None           # Set by show_monitoring — used for live ΔSPR
        self._wash_channels: set[str] = set()  # Channels in WASH state
        self._keep_alive: bool = False    # If True, suppress auto-done after first detection (P4SPR wash mode)
        self._injection_spr: dict[str, float] = {}  # SPR at injection detection per channel

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
        header_hlayout.setContentsMargins(10, 8, 10, 8)
        self._header_lbl = QLabel("Manual Injection Assistant")
        self._header_lbl.setStyleSheet(
            f"font-size: {_FS.px(15)}px; font-weight: 700; color: #1D1D1F;"
            f" font-family: {_FONT}; letter-spacing: -0.2px;"
            f" background: transparent; border: none;"
        )
        self._header_lbl.setMinimumWidth(130)
        header_hlayout.addWidget(self._header_lbl)
        header_hlayout.addStretch()
        outer.addWidget(header_row)

        # ── READY BANNER — shown when monitoring and waiting for injection ────
        # Two-line: large action line + small sub-prompt. Hidden in all other states.
        self._ready_banner = QFrame()
        self._ready_banner.setObjectName("ReadyBanner")
        self._ready_banner.setStyleSheet(
            "QFrame#ReadyBanner {"
            "  background: #34C759;"
            "  border: none;"
            "}"
        )
        _banner_vlayout = QVBoxLayout(self._ready_banner)
        _banner_vlayout.setContentsMargins(10, 7, 10, 7)
        _banner_vlayout.setSpacing(1)
        _banner_title = QLabel("Sensor Ready — Inject your sample")
        _banner_title.setStyleSheet(
            f"font-size: {_FS.px(13)}px; font-weight: 800; color: #FFFFFF;"
            f" font-family: {_FONT}; letter-spacing: 0.5px;"
            f" background: transparent; border: none;"
        )
        _banner_vlayout.addWidget(_banner_title)
        self._ready_banner.setVisible(False)
        outer.addWidget(self._ready_banner)

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
        col_hlayout.setSpacing(10)
        _col_style = (
            f"font-size: {_FS.px(12)}px; font-weight: 700; color: #8E8E93;"
            f" font-family: {_FONT}; letter-spacing: 0.8px;"
            f" border: none; background: transparent;"
        )
        _time_h = QLabel("TIME")
        _time_h.setFixedWidth(38)
        _time_h.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        _time_h.setStyleSheet(_col_style)
        col_hlayout.addWidget(_time_h)
        _ch_h = QLabel("CH")
        _ch_h.setFixedWidth(32)
        _ch_h.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
        _ch_h.setStyleSheet(_col_style)
        col_hlayout.addWidget(_ch_h)
        _action_h = QLabel("STATUS")
        _action_h.setFixedWidth(88)
        _action_h.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        _action_h.setStyleSheet(_col_style + " margin-left: 8px;")
        col_hlayout.addWidget(_action_h)
        _conc_h = QLabel("CONC")
        _conc_h.setFixedWidth(65)
        _conc_h.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        _conc_h.setStyleSheet(_col_style)
        col_hlayout.addWidget(_conc_h)
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
            row_layout.setContentsMargins(10, 5, 10, 5)
            row_layout.setSpacing(10)

            # Per-channel contact countdown label — always in layout, blank when inactive
            timer_lbl = QLabel("")
            timer_lbl.setAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            timer_lbl.setStyleSheet(
                f"font-size: {_FS.px(15)}px; font-weight: 700; color: #AF52DE;"
                f" font-family: {_MONO};"
                f" border: none; background: transparent;"
            )
            timer_lbl.setFixedWidth(38)
            row_layout.addWidget(timer_lbl)
            self._ch_timer_labels[ch] = timer_lbl

            # Channel badge — circle with letter inside, color = state
            bw = ChannelBindingWidget(ch)
            bw.setFixedSize(32, 32)
            bw.state_override_requested.connect(self._on_channel_state_override)
            row_layout.addWidget(bw)
            self._channel_widgets[ch] = bw

            # Status label (left-aligned, stretch) — shows Ready / Contact / Wash / —
            status_lbl = QLabel("\u2014")
            status_lbl.setAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            status_lbl.setStyleSheet(
                f"font-size: {_FS.px(14)}px; font-weight: 600; color: #3A3A3C; font-family: {_FONT};"
                f" border: none; background: transparent; margin-left: 8px;"
            )
            status_lbl.setFixedWidth(88)
            row_layout.addWidget(status_lbl)
            self._channel_role_labels[ch] = status_lbl

            # Concentration label (right-aligned) — always in layout, blank when not set
            conc_lbl = QLabel("")
            conc_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            conc_lbl.setStyleSheet(
                f"font-size: {_FS.px(12)}px; font-weight: 500; color: {_MUTED}; font-family: {_MONO};"
                f" border: none; background: transparent;"
            )
            conc_lbl.setFixedWidth(65)
            row_layout.addWidget(conc_lbl)
            self._ch_conc_labels[ch] = conc_lbl

            channels_vlayout.addWidget(row_frame)

        # Legend strip — explains circle colors
        legend = QLabel(
            '<span style="color:#34C759;">\u25cf</span> ready\u2003'
            '<span style="color:#AF52DE;">\u25cf</span> binding\u2003'
            '<span style="color:#5AC8FA;">\u25cf</span> wash'
        )
        legend.setTextFormat(Qt.TextFormat.RichText)
        legend.setAlignment(Qt.AlignmentFlag.AlignCenter)
        legend.setStyleSheet(
            f"font-size: {_FS.px(13)}px; color: #AEAEB2; font-family: {_MONO};"
            f" border-top: 1px solid rgba(0,0,0,0.06);"
            f" background: transparent; padding: 4px 0 4px 0;"
        )
        channels_vlayout.addWidget(legend)

        outer.addWidget(channels_container)

        # Stub attributes — kept so existing call sites don't crash.
        class _Stub:
            def __getattr__(self, _): return lambda *a, **kw: None
        self._stack        = _Stub()
        self._idle_lbl     = _Stub()
        self._idle_sub     = _Stub()
        self._label        = _Stub()
        self._status_label = _Stub()
        self._timer_label  = _Stub()
        self._row2_widget  = _Stub()

        # Hidden spacer to preserve layout height
        _spacer = QFrame()
        _spacer.setFixedHeight(4)
        _spacer.setStyleSheet("background: transparent; border: none;")
        outer.addWidget(_spacer)

    # ── Public API ────────────────────────────────────────────────────────────

    def set_panel_active(self, active: bool) -> None:
        """Activate or deactivate the Manual Injection Assistant panel.

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

    def show_monitoring(
        self,
        channels: str,
        on_done: Callable,
        on_cancel: Callable,
        contact_time: Optional[float] = None,
        buffer_mgr=None,
        keep_alive: bool = False,
        concentrations: dict | None = None,
        conc_units: str = "nM",
    ) -> None:
        """Enter monitoring state immediately — no phase 1 countdown.

        The _InjectionMonitor drives detection. This panel just shows state.

        Args:
            channels: Uppercase string of channels to monitor, e.g. "ABCD"
            on_done: Called when all channels wash or coordinator signals complete
            on_cancel: Called when coordinator cancels
            contact_time: Per-channel contact time in seconds (countdown shown after detection)
            keep_alive: If True, suppress the 1500ms auto-done after first detection.
                        Use for P4SPR where wash (fire #2) must be detected before completing.
        """
        if not self._panel_active:
            self.set_panel_active(True)
        self._on_done_cb = on_done
        self._on_cancel_cb = on_cancel
        self._first_detection_fired = False
        self._active_channels = set(channels.upper())
        self._detected_channels = set()

        self._buffer_mgr = buffer_mgr
        self._wash_channels = set()
        self._injection_spr = {}
        self._keep_alive = keep_alive
        self._timer.stop()
        self._window_start = time.time()
        self._contact_countdown = int(contact_time) if contact_time else None

        self._set_channel_colors_for_phase1()
        self._set_bar_idle_appearance()

        # Populate per-channel concentration labels
        concs = concentrations or {}
        for ch in _ALL_CHANNELS:
            lbl = self._ch_conc_labels.get(ch)
            if lbl is None:
                continue
            val = concs.get(ch.upper()) or concs.get(ch.lower())
            if val is not None:
                try:
                    fval = float(val)
                    text = f"{int(fval)} {conc_units}" if fval == int(fval) else f"{fval} {conc_units}"
                except (ValueError, TypeError):
                    text = str(val)
                lbl.setText(text)
            else:
                lbl.setText("")

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
                self._set_role_label_color(ch, _BINDING)  # purple for binding
                self._set_channel_action(ch, "Binding")
                self._detected_channels.add(ch)  # Track which channels actually detected
                # SPR baseline is set externally via set_injection_baseline() from _pump_mixin
                # when the injection flag is placed (uses time-matched SPR at t_fire, not spr[-1])
                # Start per-channel countdown if contact_time is configured
                if self._contact_countdown and self._ch_remaining.get(ch, 0) <= 0:
                    self._start_channel_countdown(ch, self._contact_countdown)
            elif ch in self._active_channels:
                bw.set_state(ChannelState.PENDING)
                self._set_role_label_color(ch, _GREEN)
            else:
                bw.set_state(ChannelState.INACTIVE)
                self._set_role_label_color(ch, _MUTED)

        # STATUS column is updated live by _refresh_delta_spr() on each tick

        if detected and not self._first_detection_fired:
            self._first_detection_fired = True
            # Hide INJECT NOW banner — injection has happened
            if hasattr(self, '_ready_banner'):
                self._ready_banner.setVisible(False)
            if self._contact_countdown is None and not self._keep_alive:
                # No contact time and not waiting for wash — auto-complete after brief visual delay
                QTimer.singleShot(1500, self._fire_done)

    def set_injection_baseline(self, channel: str, spr_at_injection: float) -> None:
        """Set the SPR baseline for ΔSPR display for a detected channel.

        Called from _pump_mixin._place_injection_flag() with the time-matched SPR
        value at t_fire (backtracked by CONFIRM_FRAMES), so ΔSPR = 0 at injection.
        """
        self._injection_spr[channel.upper()] = spr_at_injection

    def has_injection_baseline(self, channel: str) -> bool:
        return channel.upper() in self._injection_spr

    def set_injection_baseline_from_current(self, channel: str) -> None:
        """Snapshot the most recent SPR value as the injection baseline for this channel.

        Used when the user manually overrides a channel to CONTACT state without a
        hardware-detected injection event. Falls back to 0 if no SPR data available.
        """
        ch = channel.upper()
        try:
            mw = getattr(self.parent(), 'main_window', self.parent())
            cycle_data = getattr(mw, '_current_cycle_data', None) or {}
            cd = cycle_data.get(ch.lower())
            if cd is not None and hasattr(cd, 'spr') and len(cd.spr) > 0:
                self._injection_spr[ch] = float(cd.spr[-1])
                return
        except Exception:
            pass
        self._injection_spr[ch] = 0.0

    def set_channel_wash(self, channel: str) -> None:
        """Transition a channel to the WASH state (sky-blue dot).

        The bar stays in WASH state indefinitely — it does NOT auto-dismiss.
        The coordinator calls reset_for_next_injection() when fire #3 (next
        injection) is detected, which resets all channels back to PENDING.
        """
        ch = channel.upper()
        bw = self._channel_widgets.get(ch)
        if bw:
            bw.set_state(ChannelState.WASH)
            self._set_role_label_color(ch, "#5AC8FA")
        self._wash_channels.add(ch)
        self._set_channel_action(ch, "Wash")
        self._stop_channel_countdown(ch)

    def _on_channel_state_override(self, channel: str, new_state: str) -> None:
        """Apply a user-requested state override from the right-click menu.

        Updates the badge visual immediately and emits channel_state_override
        so the InjectionCoordinator can sync its internal tracking state.
        """
        ch = channel.upper()
        bw = self._channel_widgets.get(ch)
        if not bw:
            return

        bw.set_state(new_state)

        # Sync supporting UI (role label, wash tracking, countdown)
        _label_map = {
            ChannelState.PENDING:  ("Ready",    "#34C759"),
            ChannelState.CONTACT:  ("Contact",  "#AF52DE"),
            ChannelState.WASH:     ("Wash",     "#5AC8FA"),
            ChannelState.INACTIVE: ("—",        "#8E8E93"),
        }
        label, color = _label_map.get(new_state, ("—", "#8E8E93"))
        self._set_channel_action(ch, label)
        self._set_role_label_color(ch, color)

        if new_state == ChannelState.WASH:
            self._wash_channels.add(ch)
            self._stop_channel_countdown(ch)
        elif new_state == ChannelState.CONTACT:
            pass  # countdown + baseline managed externally
        else:  # PENDING or INACTIVE — undo any injection tracking
            self._wash_channels.discard(ch)
            self._stop_channel_countdown(ch)
            self._injection_spr.pop(ch, None)
            self._detected_channels.discard(ch)

        # Notify coordinator
        self.channel_state_override.emit(ch, new_state)

    def reset_for_next_injection(self) -> None:
        """Reset bar from WASH state back to PENDING — ready for next injection.

        Called by coordinator on fire #3 (next sample injection detected after
        a wash cycle). Clears all ΔSPR baselines and wash state so the Contact
        Monitor is fresh for the incoming injection.
        """
        self._wash_channels.clear()
        self._injection_spr.clear()
        self._detected_channels.clear()
        self._first_detection_fired = False
        # Reset all active channels to PENDING (yellow), inactive to grey
        for ch, bw in self._channel_widgets.items():
            if ch in self._active_channels:
                bw.set_state(ChannelState.PENDING)
                self._set_role_label_color(ch, _GREEN)
                self._set_channel_action(ch, "Ready")
            else:
                bw.set_state(ChannelState.INACTIVE)
                self._set_role_label_color(ch, _MUTED)
                self._set_channel_action(ch, "\u2014")
        # Show INJECT NOW banner — ready for next injection
        if hasattr(self, '_ready_banner'):
            self._ready_banner.setVisible(True)

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
            f"font-size: {_FS.px(13)}px; font-weight: 600; color: {_TEXT}; font-family: {_FONT};"
        )
        self._idle_sub.setVisible(True)
        # Pre-light the channels yellow so user sees which channels are active
        active = set(channels.upper())
        for ch, bw in self._channel_widgets.items():
            if ch in active:
                bw.set_state(ChannelState.PENDING)
                self._set_role_label_color(ch, _GREEN)
            else:
                bw.set_state(ChannelState.INACTIVE)
                self._set_role_label_color(ch, _MUTED)

    def update_status(self, text: str) -> None:
        """Update the Phase 2 status line (neutral colour)."""
        self._status_label.setText(text)
        self._status_label.setStyleSheet(
            f"font-size: {_FS.px(13)}px; color: {_GREEN}; font-family: {_FONT};"
        )

    def update_readiness(self, verdict: str, message: str) -> None:
        """No-op - readiness is shown per-channel in the STATUS column."""
        pass

    def set_channel_role(self, channel: str, role: str) -> None:
        """No-op — kept for backward compat. Status is now purely action-based."""
        pass

    def _set_channel_action(self, channel: str, action: str) -> None:
        """Update the STATUS column text for a channel.

        Always shows the action state: Ready / Contact / Wash / — .
        This is a pure user-action UI — no sample info shown here.
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
        # Return to dormant — panel greys out until next binding cycle
        self._panel_active = False
        self._apply_dormant_appearance()

    # ── Internal helpers ───────────────────────────────────────────────────────


    def _set_role_label_color(self, ch: str, color: str) -> None:
        lbl = self._channel_role_labels.get(ch)
        if lbl:
            lbl.setStyleSheet(
                f"font-size: {_FS.px(12)}px; font-weight: 600; color: {color}; font-family: {_FONT};"
                f" border: none; background: transparent;"
            )

    def _set_channel_colors_for_phase1(self) -> None:
        for ch, bw in self._channel_widgets.items():
            if ch in self._active_channels:
                bw.set_state(ChannelState.PENDING)
                self._set_role_label_color(ch, _GREEN)
                self._set_channel_action(ch, "Ready")
            else:
                bw.set_state(ChannelState.INACTIVE)
                self._set_role_label_color(ch, _MUTED)
                self._set_channel_action(ch, "\u2014")
        # Show INJECT NOW banner — all channels waiting
        if hasattr(self, '_ready_banner'):
            self._ready_banner.setVisible(True)

    def _reset_all_leds(self) -> None:
        for ch, bw in self._channel_widgets.items():
            bw.set_state(ChannelState.INACTIVE)
            self._set_role_label_color(ch, _MUTED)
            self._stop_channel_countdown(ch)
            lbl = self._ch_conc_labels.get(ch)
            if lbl:
                lbl.setText("")

    # ── Per-channel countdown logic ───────────────────────────────────────────

    def _start_channel_countdown(self, ch: str, total_seconds: int) -> None:
        """Begin an independent contact-time countdown for one channel."""
        self._ch_remaining[ch] = total_seconds
        lbl = self._ch_timer_labels.get(ch)
        if lbl:
            lbl.setText(self._fmt_time(total_seconds))
            _init_clr = _TIMER_OK if total_seconds > 30 else (_TIMER_WARN if total_seconds > 10 else _TIMER_CRIT)
            lbl.setStyleSheet(
                f"font-size: {_FS.px(14)}px; font-weight: 800; color: {_init_clr};"
                f" font-family: {_MONO};"
                f" border: none; background: transparent;"
            )
        self._ch_timers[ch].start()

    def _stop_channel_countdown(self, ch: str) -> None:
        """Stop a channel's countdown and clear the label."""
        timer = self._ch_timers.get(ch)
        if timer:
            timer.stop()
        self._ch_remaining[ch] = 0
        lbl = self._ch_timer_labels.get(ch)
        if lbl:
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
            # Contact time just expired — transition to WASH state and signal upstream
            self.channel_countdown_complete.emit(ch)
            self.set_channel_wash(ch)

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
            if remaining > 30:
                color = _TIMER_OK        # green — comfortable
            elif remaining > 10:
                color = _TIMER_WARN      # orange — getting close
            elif remaining > 0:
                color = _TIMER_CRIT      # red — last 10 seconds
            elif remaining == 0:
                color = _TIMER_CRIT      # red — boundary
            else:
                color = _TIMER_CRIT      # red — overrunning (wash not yet done)
            lbl.setStyleSheet(
                f"font-size: {_FS.px(14)}px; font-weight: 800; color: {color};"
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

    def get_max_contact_remaining(self) -> tuple[int, str] | None:
        """Return (remaining_sec, channel) for the binding channel with the most time left.

        Returns None if no channel has an active countdown (no injection detected yet,
        or no contact time configured). Negative values indicate overrun.
        Used by CycleStatusOverlay to show the contact timer as the primary display.
        The channel letter lets the overlay label which channel the timer belongs to.
        """
        if not self._detected_channels:
            return None
        pairs = [(self._ch_remaining.get(ch, 0), ch) for ch in self._detected_channels
                 if self._ch_timers.get(ch) and self._ch_timers[ch].isActive()]
        if not pairs:
            return None
        best = max(pairs, key=lambda x: x[0])
        return (best[0], best[1])

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
        to signal that the Manual Injection Assistant is inactive.

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
        # Header stays visible in dormant — only colour dims slightly
        if hasattr(self, '_header_lbl'):
            self._header_lbl.setStyleSheet(
                f"font-size: {_FS.px(15)}px; font-weight: 700; color: #86868B;"
                f" font-family: {_FONT}; letter-spacing: -0.2px;"
                f" background: transparent; border: none;"
            )
        # Dim idle text — also hide sub-label to prevent state bleed
        if hasattr(self, '_idle_lbl'):
            self._idle_lbl.setText("Waiting for binding cycle")
            self._idle_lbl.setStyleSheet(
                f"font-size: 12px; color: #C7C7CC; font-family: {_FONT};"
            )
        if hasattr(self, '_idle_sub'):
            self._idle_sub.setVisible(False)
        # Hide INJECT NOW banner — panel is dormant
        if hasattr(self, '_ready_banner'):
            self._ready_banner.setVisible(False)
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
        # Restore header — full dark when active
        if hasattr(self, '_header_lbl'):
            self._header_lbl.setStyleSheet(
                f"font-size: {_FS.px(15)}px; font-weight: 700; color: #1D1D1F;"
                f" font-family: {_FONT}; letter-spacing: -0.2px;"
                f" background: transparent; border: none;"
            )
        # Restore idle label
        if hasattr(self, '_idle_lbl'):
            self._idle_lbl.setText("Monitoring — awaiting injection")
            self._idle_lbl.setStyleSheet(
                f"font-size: 12px; color: {_MUTED}; font-family: {_FONT};"
            )
        # Restore channel labels to normal muted
        for ch in _ALL_CHANNELS:
            self._set_role_label_color(ch, _MUTED)

    # ── Timer tick ────────────────────────────────────────────────────────────

    def _tick(self) -> None:
        if self._window_start is not None:
            elapsed = int(time.time() - self._window_start)
            m, s = divmod(elapsed, 60)
            self._timer_label.setText(f"{m:02d}:{s:02d}")

        # Update per-channel ΔSPR in STATUS column
        self._refresh_delta_spr()

    def _refresh_delta_spr(self) -> None:
        """Update STATUS labels for detected channels only.

        PENDING channels (pre-injection) are NOT touched here — their "Ready"
        text is set by _set_channel_colors_for_phase1 and must persist.
        Only channels that have had injection baseline set (post-detection)
        get live ΔSPR updates. Wash channels stay on "Wash".
        """
        if self._buffer_mgr is None:
            return
        try:
            cycle_data = getattr(self._buffer_mgr, 'cycle_data', None)
            if cycle_data is None:
                return
            for ch in _ALL_CHANNELS:
                lbl = self._channel_role_labels.get(ch)
                if lbl is None:
                    continue
                # Wash: static label set by set_channel_wash — don't overwrite
                if ch in self._wash_channels:
                    continue
                # Not detected yet — leave "Ready" label alone
                if ch not in self._injection_spr:
                    continue
                # Post-injection: show live ΔSPR
                cd = cycle_data.get(ch.lower())
                if cd is None or not hasattr(cd, 'spr') or len(cd.spr) == 0:
                    continue
                delta = float(cd.spr[-1]) - self._injection_spr[ch]
                sign = "+" if delta >= 0 else ""
                lbl.setText(f"{sign}{delta:.0f} RU")
        except Exception:
            pass

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

    def _fire_done(self) -> None:
        self._timer.stop()
        # Stop all per-channel timers
        for ch in _ALL_CHANNELS:
            self._stop_channel_countdown(ch)
        self._active_channels.clear()
        self._detected_channels.clear()
        self._first_detection_fired = False
        self._reset_all_leds()
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
        # Show missed message per-channel in STATUS column
        for ch in self._active_channels:
            self._set_channel_action(ch, "Not detected")
            self._set_role_label_color(ch, "#FF9500")
        # Auto-dismiss after 8s so the bar doesn't stay forever
        from PySide6.QtCore import QTimer as _QTimer
        _QTimer.singleShot(8000, lambda: self.set_panel_active(False))

    def show_mislabel_warning(self, detected_channels: str, expected_channels: str) -> None:
        """Flash an orange warning when injection detected on unexpected channels.

        Args:
            detected_channels: e.g. "C, D"
            expected_channels: e.g. "A, B"
        """
        # Mislabel warning not applicable in per-channel STATUS model
        pass
