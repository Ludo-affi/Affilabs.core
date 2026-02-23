"""Cycle Intelligence Footer Widget — status and live-clock bar below Active Cycle graph.

LAYOUT  (left → stretch → centre → stretch → right)
  Left  : cycle metadata — name · type · duration · sample · concentration
  Centre: experiment elapsed clock  +  recording elapsed clock (shown only when recording)
  Right : signal science — λ resonance · FWHM · p2p baseline noise · slope · Stable/Drifting
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QWidget,
)

from affilabs.utils.logger import logger

# ── Typography constants matching the app design system ──────────────────────
_FONT = "-apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif"
_MONO = "'SF Mono', 'Cascadia Code', 'Consolas', monospace"

# ── Status dot colours ────────────────────────────────────────────────────────
_DOT_GREY   = "#C7C7CC"
_DOT_GREEN  = "#34C759"
_DOT_ORANGE = "#FF9500"
_DOT_RED    = "#FF3B30"


def _fmt_elapsed(seconds: float) -> str:
    """Format raw seconds as HH:MM:SS."""
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"


class CycleIntelligenceFooter(QFrame):
    """Slim footer bar below the Active Cycle graph.

    Displays:
    - Left  : current cycle metadata (scrolling marquee if long)
    - Centre: live experiment elapsed + recording elapsed (when active)
    - Right : signal science indicators — λ, FWHM, p2p noise, baseline stability

    Public API
    ----------
    update_cycle_info(cycle_data)                          — call when active cycle changes
    update_status(status_data)                             — kept for backward compat (no-op)
    update_signal_metrics(ch, wavelength, fwhm, p2p, stable) — call from coordinator per IQ update
    set_clock_getter(fn)                                   — callable returning (exp_s, rec_s|None)
    set_recording_active(active)                           — show/hide rec clock
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.cycle_data: dict[str, Any] | None = None
        self.status_data: dict[str, str | int] = {}  # kept for compat; not used in right panel
        self._clock_getter: Callable[[], tuple[float, float | None]] | None = None
        self._recording_active: bool = False
        self._full_metadata_text: str = ""
        self._scroll_offset: int = 0
        # Latest signal metrics per channel (lower-case key)
        self._signal_metrics: dict[str, dict] = {}

        self.setMinimumHeight(36)
        self.setMaximumHeight(40)
        self.setObjectName("CycleFooter")
        self.setStyleSheet(
            "QFrame#CycleFooter {"
            "  background: #FAFAFA;"
            "  border-top: 1px solid #E5E5EA;"
            "}"
        )

        self._setup_ui()

        # Marquee scroll timer (30 ms ≈ 33 fps, very smooth)
        self._scroll_timer = QTimer(self)
        self._scroll_timer.timeout.connect(self._auto_scroll_step)

        # Live-clock update (every second)
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clocks)
        self._clock_timer.start(1000)

    # ── Construction ──────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(12, 4, 12, 4)
        root.setSpacing(0)

        # ── Left: metadata label ──────────────────────────────────────────────
        self._metadata_label = QLabel("No cycle loaded")
        self._metadata_label.setStyleSheet(
            f"font-size: 11px; color: #8E8E93;"
            f"font-family: {_FONT}; background: transparent;"
        )
        self._metadata_label.setTextFormat(Qt.TextFormat.PlainText)
        root.addWidget(self._metadata_label, 1)

        root.addSpacing(12)
        root.addWidget(self._vdiv())
        root.addSpacing(12)

        # ── Centre: clocks ────────────────────────────────────────────────────
        clocks_row = QHBoxLayout()
        clocks_row.setSpacing(10)
        clocks_row.setContentsMargins(0, 0, 0, 0)
        self._clocks_row_layout = clocks_row  # retained so show_saved_toast can insert into it

        # Experiment elapsed
        exp_prefix = QLabel("Exp")
        exp_prefix.setStyleSheet(
            f"font-size: 10px; color: #8E8E93; font-family: {_FONT}; background: transparent;"
        )
        clocks_row.addWidget(exp_prefix)

        self._exp_clock = QLabel("—")
        self._exp_clock.setStyleSheet(
            f"font-size: 11px; font-weight: 600; color: #1D1D1F;"
            f"font-family: {_MONO}; background: transparent; min-width: 46px;"
        )
        self._exp_clock.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        clocks_row.addWidget(self._exp_clock)

        clocks_row.addSpacing(12)

        # Recording elapsed (hidden until recording starts)
        self._rec_dot = QLabel("●")
        self._rec_dot.setStyleSheet(
            f"font-size: 9px; color: {_DOT_RED}; font-family: {_FONT}; background: transparent;"
        )
        self._rec_dot.setVisible(False)

        self._rec_label = QLabel("Rec")
        self._rec_label.setStyleSheet(
            f"font-size: 10px; color: #8E8E93; font-family: {_FONT}; background: transparent;"
        )
        self._rec_label.setVisible(False)

        self._rec_clock = QLabel("00:00")
        self._rec_clock.setStyleSheet(
            f"font-size: 11px; font-weight: 600; color: {_DOT_RED};"
            f"font-family: {_MONO}; background: transparent; min-width: 38px;"
        )
        self._rec_clock.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._rec_clock.setVisible(False)

        clocks_row.addWidget(self._rec_dot)
        clocks_row.addWidget(self._rec_label)
        clocks_row.addWidget(self._rec_clock)

        root.addLayout(clocks_row)

        root.addSpacing(12)
        root.addWidget(self._vdiv())
        root.addSpacing(12)

        # ── Right: signal science indicators ─────────────────────────────────
        # λ · FWHM · p2p noise · Baseline stability
        sig_row = QHBoxLayout()
        sig_row.setSpacing(14)
        sig_row.setContentsMargins(0, 0, 0, 0)

        def _metric_pair(prefix: str, value: str, tooltip: str) -> tuple[QLabel, QLabel]:
            """Return (prefix_label, value_label) added to sig_row."""
            lbl_p = QLabel(prefix)
            lbl_p.setStyleSheet(
                f"font-size: 10px; color: #8E8E93; font-family: {_FONT}; background: transparent;"
            )
            lbl_v = QLabel(value)
            lbl_v.setStyleSheet(
                f"font-size: 11px; font-weight: 600; color: #1D1D1F;"
                f"font-family: {_MONO}; background: transparent;"
            )
            lbl_v.setToolTip(tooltip)
            inner = QHBoxLayout()
            inner.setSpacing(4)
            inner.setContentsMargins(0, 0, 0, 0)
            inner.addWidget(lbl_p)
            inner.addWidget(lbl_v)
            sig_row.addLayout(inner)
            return lbl_p, lbl_v

        _, self._wl_val   = _metric_pair("λ",    "—",  "Resonance wavelength of active channel (nm)")
        _, self._fwhm_val = _metric_pair("FWHM", "—",  "SPR dip width — narrower = better coupling (nm)")
        _, self._p2p_val  = _metric_pair("p2p",  "—",  "Baseline noise: peak-to-peak over last ~10 s\n"
                                                        "<5 nm = stable  ·  5–8 nm = noisy  ·  >8 nm = poor")
        _, self._slope_val = _metric_pair("slope", "—", "60 s baseline slope (nm/s) — baseline & auto-read only\n"
                                                        "Drift threshold: 10 RU / 15 min (355 RU = 1 nm → ≈ ±3.1e-5 nm/s)")

        # Baseline stability pill (dot + text)
        self._stab_dot  = QLabel("●")
        self._stab_dot.setStyleSheet(
            f"font-size: 9px; color: {_DOT_GREY}; font-family: {_FONT}; background: transparent;"
        )
        self._stab_text = QLabel("—")
        self._stab_text.setStyleSheet(
            f"font-size: 11px; color: #8E8E93; font-family: {_FONT}; background: transparent;"
        )
        self._stab_text.setToolTip("Baseline stability — green = ready to inject")
        stab_grp = QHBoxLayout()
        stab_grp.setSpacing(4)
        stab_grp.setContentsMargins(0, 0, 0, 0)
        stab_grp.addWidget(self._stab_dot)
        stab_grp.addWidget(self._stab_text)
        sig_row.addLayout(stab_grp)

        root.addLayout(sig_row)

    @staticmethod
    def _vdiv() -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.Shape.VLine)
        f.setFixedWidth(1)
        f.setStyleSheet("background: #E5E5EA; margin: 4px 0;")
        return f

    # ── Public API ────────────────────────────────────────────────────────────

    def set_clock_getter(self, fn: Callable[[], tuple[float, float | None]]) -> None:
        """Register a callable that returns (exp_elapsed_secs, rec_elapsed_secs | None).

        Called once per second by the internal clock timer.
        """
        self._clock_getter = fn

    def set_recording_active(self, active: bool) -> None:
        """Show or hide the recording elapsed clock."""
        self._recording_active = active
        self._rec_dot.setVisible(active)
        self._rec_label.setVisible(active)
        self._rec_clock.setVisible(active)
        if not active:
            self._rec_clock.setText("00:00")

    def show_saved_toast(self, filename: str, on_click: Callable[[], None] | None = None) -> None:
        """Replace the rec clock area with a brief '✓ Saved' notice.

        The label is clickable (navigates to Edits tab via *on_click*) and
        auto-hides after 8 seconds, restoring normal empty state.

        Args:
            filename: Just the file basename to display.
            on_click: Optional callable invoked when the user clicks the label.
        """
        # Hide rec widgets (recording is already stopped at this point)
        self._rec_dot.setVisible(False)
        self._rec_label.setVisible(False)
        self._rec_clock.setVisible(False)

        # Create the toast label lazily
        if not hasattr(self, '_saved_toast_label'):
            lbl = QLabel()
            lbl.setTextFormat(Qt.TextFormat.PlainText)
            lbl.setCursor(Qt.CursorShape.PointingHandCursor)
            lbl.setStyleSheet(
                f"font-size: 11px; font-weight: 600; color: {_DOT_GREEN};"
                f"font-family: {_FONT}; background: transparent;"
                "text-decoration: underline;"
            )
            # Insert into the root layout (after rec widgets)
            if hasattr(self, '_clocks_row_layout'):
                self._clocks_row_layout.addWidget(lbl)
            else:
                self.layout().addWidget(lbl)
            self._saved_toast_label = lbl
            self._saved_toast_timer = QTimer(self)
            self._saved_toast_timer.setSingleShot(True)
            self._saved_toast_timer.timeout.connect(self._hide_saved_toast)

        self._saved_toast_label.setText(f"✓ Saved — View results →")
        self._saved_toast_label.setToolTip(filename)

        # Wire click — disconnect any previous connection first
        try:
            self._saved_toast_label.mousePressEvent = None
        except Exception:
            pass
        if on_click:
            self._saved_toast_label.mousePressEvent = lambda __e: on_click()

        self._saved_toast_label.setVisible(True)
        self._saved_toast_timer.start(8000)

    def _hide_saved_toast(self) -> None:
        """Auto-dismiss the saved toast."""
        if hasattr(self, '_saved_toast_label'):
            self._saved_toast_label.setVisible(False)

    def update_cycle_info(self, cycle_data: dict[str, Any] | None) -> None:
        """Update the cycle metadata label."""
        self.cycle_data = cycle_data
        self._update_metadata_display()

    def update_status(self, status_data: dict[str, Any]) -> None:
        """Kept for backward compatibility — signal metrics now drive the right panel."""
        self.status_data.update(status_data)

    def update_signal_metrics(
        self,
        channel: str,
        wavelength: float | None,
        fwhm: float | None,
        p2p: float | None,
        stable: bool | None,
        slope: float | None = None,
    ) -> None:
        """Update signal science indicators from the active timing channel.

        Args:
            channel  : Channel letter ('a'–'d'); only the selected timing channel is shown.
            wavelength: Resonance wavelength in nm, or None.
            fwhm     : SPR dip FWHM in nm, or None.
            p2p      : Baseline peak-to-peak noise in nm over last ~10 s, or None.
            stable   : True = baseline stable, False = drifting, None = unknown.
            slope    : 10 s baseline slope in nm/s, or None. Positive = rising, negative = falling.
        """
        ch = channel.lower()
        self._signal_metrics[ch] = {
            'wavelength': wavelength,
            'fwhm': fwhm,
            'p2p': p2p,
            'stable': stable,
            'slope': slope,
        }
        self._refresh_signal_panel(ch)

    # ── Internal: clock tick ──────────────────────────────────────────────────

    def _update_clocks(self) -> None:
        if self._clock_getter is None:
            return
        try:
            exp_elapsed, rec_elapsed = self._clock_getter()
        except Exception:
            return

        if exp_elapsed is None or exp_elapsed <= 0:
            self._exp_clock.setText("—")
        else:
            self._exp_clock.setText(_fmt_elapsed(exp_elapsed))

        if self._recording_active and rec_elapsed is not None and rec_elapsed >= 0:
            self._rec_clock.setText(_fmt_elapsed(rec_elapsed))

    # ── Internal: metadata ────────────────────────────────────────────────────

    def _update_metadata_display(self) -> None:
        self._scroll_timer.stop()
        self._scroll_offset = 0

        if not self.cycle_data:
            self._metadata_label.setText("No cycle loaded")
            self._metadata_label.setStyleSheet(
                f"font-size: 11px; color: #8E8E93; font-family: {_FONT}; background: transparent;"
            )
            self._full_metadata_text = ""
            return

        parts = []
        name = self.cycle_data.get('name', 'Unknown')
        cycle_type = self.cycle_data.get('type', '')
        if cycle_type:
            parts.append(f"{name}  ({cycle_type})")
        else:
            parts.append(name)

        dur = self.cycle_data.get('duration_minutes', 0)
        if dur:
            parts.append(f"{dur:.0f} min")

        sample_id = self.cycle_data.get('sample_id')
        if sample_id:
            parts.append(sample_id)

        conc = self.cycle_data.get('concentration')
        if conc is not None:
            units = self.cycle_data.get('units', 'nM')
            parts.append(f"{conc} {units}")

        channels = self.cycle_data.get('channels')
        if channels:
            parts.append(f"Ch {channels}")

        note = self.cycle_data.get('note')
        if note:
            parts.append(f'"{note}"')

        self._full_metadata_text = "  ·  ".join(parts)
        self._metadata_label.setText(self._full_metadata_text)
        self._metadata_label.setStyleSheet(
            f"font-size: 11px; color: #1D1D1F; font-family: {_FONT}; background: transparent;"
        )
        QTimer.singleShot(800, self._check_and_start_autoscroll)

    def _check_and_start_autoscroll(self) -> None:
        if not self._full_metadata_text:
            return
        label_w = self._metadata_label.sizeHint().width()
        parent_w = self._metadata_label.parent().width() if self._metadata_label.parent() else 0
        if parent_w > 0 and label_w > parent_w:
            self._scroll_timer.start(60)

    def _auto_scroll_step(self) -> None:
        if not self._full_metadata_text:
            self._scroll_timer.stop()
            return
        spacer = "        "
        full_loop = self._full_metadata_text + spacer
        loop_len = len(full_loop)
        self._scroll_offset = (self._scroll_offset + 1) % loop_len
        visible = (full_loop * 2)[self._scroll_offset:self._scroll_offset + len(self._full_metadata_text)]
        self._metadata_label.setText(visible)

    # ── Internal: signal panel ────────────────────────────────────────────────

    # Conversion: 355 RU = 1 nm
    # Drift threshold: 10 RU / 15 min = (10/355 nm) / 900 s ≈ 3.13e-5 nm/s
    RU_PER_NM = 355
    SLOPE_DRIFT_THRESHOLD = (10 / RU_PER_NM) / 900  # nm/s  (~3.13e-5)

    def _refresh_signal_panel(self, channel: str) -> None:
        """Refresh right-side signal science indicators for *channel*."""
        m = self._signal_metrics.get(channel, {})

        wl   = m.get('wavelength')
        fwhm = m.get('fwhm')
        p2p  = m.get('p2p')
        slope = m.get('slope')
        # stable can be overridden by slope if slope is available
        stable = m.get('stable')
        if slope is not None:
            stable = abs(slope) < self.SLOPE_DRIFT_THRESHOLD

        # λ
        self._wl_val.setText(f"{wl:.1f} nm" if wl is not None else "—")
        self._wl_val.setStyleSheet(
            f"font-size: 11px; font-weight: 600; color: {'#1D1D1F' if wl else '#8E8E93'};"
            f"font-family: {_MONO}; background: transparent;"
        )

        # FWHM
        self._fwhm_val.setText(f"{fwhm:.1f} nm" if fwhm is not None else "—")
        self._fwhm_val.setStyleSheet(
            f"font-size: 11px; font-weight: 600; color: {'#1D1D1F' if fwhm else '#8E8E93'};"
            f"font-family: {_MONO}; background: transparent;"
        )

        # p2p — colour-coded
        if p2p is None:
            p2p_color = "#8E8E93"
            p2p_txt = "—"
        elif p2p >= 8.0:
            p2p_color = _DOT_RED
            p2p_txt = f"±{p2p:.1f} nm"
        elif p2p >= 5.0:
            p2p_color = _DOT_ORANGE
            p2p_txt = f"±{p2p:.1f} nm"
        else:
            p2p_color = _DOT_GREEN
            p2p_txt = f"±{p2p:.1f} nm"
        self._p2p_val.setText(p2p_txt)
        self._p2p_val.setStyleSheet(
            f"font-size: 11px; font-weight: 600; color: {p2p_color};"
            f"font-family: {_MONO}; background: transparent;"
        )

        # Slope — colour-coded by magnitude vs threshold
        if slope is None:
            slope_color = "#8E8E93"
            slope_txt = "—"
        else:
            sign = "+" if slope >= 0 else ""
            slope_txt = f"{sign}{slope:.3f} nm/s"
            if abs(slope) >= self.SLOPE_DRIFT_THRESHOLD:
                slope_color = _DOT_ORANGE
            else:
                slope_color = _DOT_GREEN
        self._slope_val.setText(slope_txt)
        self._slope_val.setStyleSheet(
            f"font-size: 11px; font-weight: 600; color: {slope_color};"
            f"font-family: {_MONO}; background: transparent;"
        )

        # Baseline stability dot + text
        if stable is None:
            stab_color, stab_txt, stab_text_color = _DOT_GREY, "—", "#8E8E93"
        elif stable:
            stab_color, stab_txt, stab_text_color = _DOT_GREEN, "Stable", "#1D1D1F"
        else:
            stab_color, stab_txt, stab_text_color = _DOT_ORANGE, "Drifting", _DOT_ORANGE
        self._stab_dot.setStyleSheet(
            f"font-size: 9px; color: {stab_color}; font-family: {_FONT}; background: transparent;"
        )
        self._stab_text.setText(stab_txt)
        self._stab_text.setStyleSheet(
            f"font-size: 11px; color: {stab_text_color}; font-family: {_FONT}; background: transparent;"
        )
