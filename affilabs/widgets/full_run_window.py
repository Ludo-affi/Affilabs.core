"""Full Run Window — standalone read-only sensorgram for a loaded experiment.

Opens from the Edits tab. Reads the Channels XY sheet from the source Excel
file and plots all 4 channels over the full experiment timeline with two
draggable delta-SPR cursors.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

# Channel display colours — same as GRAPH_COLORS in settings.py
_CH_COLORS = {
    "a": "#1D1D1F",
    "b": "#FF3B30",
    "c": "#007AFF",
    "d": "#34C759",
}
_CH_LABELS = {"a": "A", "b": "B", "c": "C", "d": "D"}
_MONO = "'SF Mono', 'Cascadia Code', 'Consolas', monospace"
_FONT_FAMILY = "-apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif"


# ── Per-channel delta readout panel ───────────────────────────────────────────

class _DeltaPanel(QWidget):
    """Pill-shaped panel: Δt + per-channel ΔSPR values, styled like InteractiveSPRLegend."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DeltaPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(10)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 28))
        self.setGraphicsEffect(shadow)

        self.setStyleSheet(
            "#DeltaPanel QLabel, #DeltaPanel QWidget {"
            "  background: transparent; border: none;"
            "}"
        )

        row = QHBoxLayout(self)
        row.setContentsMargins(10, 5, 10, 5)
        row.setSpacing(0)

        # Title / Δt section
        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)

        self._title_lbl = QLabel("Δt: —")
        self._title_lbl.setFont(title_font)
        self._title_lbl.setStyleSheet(
            f"color: rgba(30,30,30,200); font-family: {_FONT_FAMILY};"
            " background: transparent; padding: 0 8px 0 0;"
        )
        row.addWidget(self._title_lbl)

        # Per-channel cells
        self._ch_labels: dict[str, QLabel] = {}
        for i, ch in enumerate("abcd"):
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.VLine)
            sep.setStyleSheet("color: rgba(0,0,0,0.10); background: transparent;")
            sep.setFixedWidth(1)
            row.addWidget(sep)

            cell = QWidget()
            cell_layout = QHBoxLayout(cell)
            cell_layout.setContentsMargins(8, 2, 8, 2)
            cell_layout.setSpacing(4)

            # Channel letter
            letter = QLabel(_CH_LABELS[ch])
            letter.setStyleSheet(
                f"color: {_CH_COLORS[ch]}; font-weight: 700; font-size: 12px;"
                f" font-family: {_FONT_FAMILY}; background: transparent;"
            )
            cell_layout.addWidget(letter)

            # Value
            val = QLabel("—")
            val.setStyleSheet(
                f"color: {_CH_COLORS[ch]}; font-weight: 600; font-size: 13px;"
                f" font-family: {_MONO}; background: transparent;"
            )
            val.setMinimumWidth(52)
            cell_layout.addWidget(val)

            row.addWidget(cell)
            self._ch_labels[ch] = val

        self.setMinimumHeight(32)
        self.setMaximumHeight(44)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(self.rect().adjusted(0, 0, -1, -1), 8, 8)
        painter.fillPath(path, QColor(255, 255, 255, 235))
        painter.setPen(QColor(0, 0, 0, 38))
        painter.drawPath(path)

    def update(self, dt: float | None, per_ch: dict[str, float | None]):
        """Update Δt label and per-channel ΔSPR values.

        Args:
            dt: time delta in seconds, or None if unknown.
            per_ch: {'a': float|None, ...} — None means channel hidden/no data.
        """
        if dt is None:
            self._title_lbl.setText("Δt: —")
        else:
            self._title_lbl.setText(f"Δt: {dt:+.1f} s")

        for ch, val in per_ch.items():
            lbl = self._ch_labels.get(ch)
            if lbl is None:
                continue
            if val is None:
                lbl.setText("—")
            else:
                sign = "+" if val >= 0 else ""
                lbl.setText(f"{sign}{val:.3f}")

    def set_channel_visible(self, ch: str, visible: bool):
        """Dim value label when channel is hidden."""
        lbl = self._ch_labels.get(ch)
        if lbl is None:
            return
        opacity = "1.0" if visible else "0.3"
        lbl.setStyleSheet(
            f"color: {_CH_COLORS[ch]}; font-weight: 600; font-size: 13px;"
            f" font-family: {_MONO}; background: transparent; opacity: {opacity};"
        )


# ── Main window ───────────────────────────────────────────────────────────────

class FullRunWindow(QDialog):
    """Non-modal dialog showing the full experiment timeline with cursors."""

    def __init__(self, source_file: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Full Run — Sensorgram")
        self.resize(1100, 560)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowMaximizeButtonHint |
            Qt.WindowType.WindowCloseButtonHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self._source_file = source_file
        self._curves: dict[str, pg.PlotDataItem] = {}
        self._cursor1: pg.InfiniteLine | None = None
        self._cursor2: pg.InfiniteLine | None = None
        self._data: dict[str, tuple[np.ndarray, np.ndarray]] = {}  # ch → (time, spr)

        self._build_ui()
        self._load_data()
        self._plot_data()
        self._add_cursors()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        # Top bar: channel toggles
        top_bar = QHBoxLayout()
        top_bar.setSpacing(12)

        self._ch_checks: dict[str, QCheckBox] = {}
        for ch in ("a", "b", "c", "d"):
            cb = QCheckBox(f"Ch {_CH_LABELS[ch]}")
            cb.setChecked(True)
            cb.setStyleSheet(
                f"QCheckBox {{ color: {_CH_COLORS[ch]}; font-weight: 600; font-size: 12px; }}"
            )
            cb.toggled.connect(lambda checked, c=ch: self._on_ch_toggle(c, checked))
            top_bar.addWidget(cb)
            self._ch_checks[ch] = cb

        top_bar.addStretch()
        root.addLayout(top_bar)

        # Plot
        pg.setConfigOptions(antialias=True, background="w", foreground="k")
        self._plot = pg.PlotWidget()
        self._plot.setLabel("bottom", "Time (s)")
        self._plot.setLabel("left", "SPR (nm)")
        self._plot.showGrid(x=True, y=True, alpha=0.15)
        self._plot.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._plot.getPlotItem().getAxis("bottom").setStyle(tickFont=QFont("SF Pro Text", 9))
        self._plot.getPlotItem().getAxis("left").setStyle(tickFont=QFont("SF Pro Text", 9))
        root.addWidget(self._plot)

        # Delta panel — below plot, left-aligned
        self._delta_panel = _DeltaPanel()
        panel_row = QHBoxLayout()
        panel_row.setContentsMargins(0, 0, 0, 0)
        panel_row.addWidget(self._delta_panel)
        panel_row.addStretch()
        root.addLayout(panel_row)

        # Status bar
        self._status_label = QLabel("Loading…")
        self._status_label.setStyleSheet("color: #8E8E93; font-size: 11px;")
        root.addWidget(self._status_label)

    # ── Data loading ──────────────────────────────────────────────────────────

    def _load_data(self):
        try:
            xl = pd.read_excel(self._source_file, sheet_name=None, engine="openpyxl")
        except Exception as e:
            self._status_label.setText(f"Failed to open file: {e}")
            return

        # Try "Channels XY" first, fall back to "Per-Channel Format"
        sheet = None
        for name in ("Channels XY", "Per-Channel Format"):
            if name in xl:
                sheet = xl[name]
                break

        if sheet is None:
            self._status_label.setText(
                "Could not find 'Channels XY' sheet in the Excel file."
            )
            return

        for ch in ("a", "b", "c", "d"):
            t_col = f"Time_{ch.upper()}"
            s_col = f"SPR_{ch.upper()}"
            if t_col in sheet.columns and s_col in sheet.columns:
                t = pd.to_numeric(sheet[t_col], errors="coerce").dropna().to_numpy(dtype=float)
                s = pd.to_numeric(sheet[s_col], errors="coerce")
                s = s.iloc[: len(t)].to_numpy(dtype=float)
                if len(t) > 0:
                    self._data[ch] = (t, s)

        n_pts = sum(len(v[0]) for v in self._data.values())
        n_ch = len(self._data)
        self._status_label.setText(
            f"{self._source_file}  ·  {n_ch} channels  ·  {n_pts:,} points  "
            "·  Drag cursors to measure Δ"
        )

    # ── Plotting ──────────────────────────────────────────────────────────────

    def _plot_data(self):
        self._plot.clear()
        self._curves.clear()

        for ch, (t, s) in self._data.items():
            color = _CH_COLORS[ch]
            curve = self._plot.plot(
                t, s,
                pen=pg.mkPen(color=color, width=1.5),
                name=f"Ch {_CH_LABELS[ch]}",
            )
            self._curves[ch] = curve

        if not self._data:
            self._status_label.setText("No channel data found in the Excel file.")

    def _on_ch_toggle(self, ch: str, visible: bool):
        if ch in self._curves:
            self._curves[ch].setVisible(visible)
        self._delta_panel.set_channel_visible(ch, visible)
        self._update_delta()

    # ── Cursors ───────────────────────────────────────────────────────────────

    def _add_cursors(self):
        if not self._data:
            return

        # Place cursors at 25% and 75% of the time axis
        all_t = np.concatenate([v[0] for v in self._data.values()])
        t_min, t_max = float(all_t.min()), float(all_t.max())
        span = t_max - t_min or 1.0

        t1 = t_min + span * 0.25
        t2 = t_min + span * 0.75

        self._cursor1 = pg.InfiniteLine(
            pos=t1, angle=90, movable=True,
            pen=pg.mkPen(color="#FF9500", width=1.5, style=Qt.PenStyle.DashLine),
            label="C1", labelOpts={"color": "#FF9500", "position": 0.95},
        )
        self._cursor2 = pg.InfiniteLine(
            pos=t2, angle=90, movable=True,
            pen=pg.mkPen(color="#AF52DE", width=1.5, style=Qt.PenStyle.DashLine),
            label="C2", labelOpts={"color": "#AF52DE", "position": 0.85},
        )
        self._cursor1.sigPositionChanged.connect(self._update_delta)
        self._cursor2.sigPositionChanged.connect(self._update_delta)
        self._plot.addItem(self._cursor1)
        self._plot.addItem(self._cursor2)
        self._update_delta()

    def _update_delta(self):
        if self._cursor1 is None or self._cursor2 is None:
            return

        t1 = self._cursor1.value()
        t2 = self._cursor2.value()
        dt = t2 - t1

        per_ch: dict[str, float | None] = {}
        for ch in ("a", "b", "c", "d"):
            if ch not in self._data or not self._ch_checks[ch].isChecked():
                per_ch[ch] = None
                continue
            t, s = self._data[ch]
            if len(t) == 0:
                per_ch[ch] = None
                continue
            s1 = float(np.interp(t1, t, s))
            s2 = float(np.interp(t2, t, s))
            per_ch[ch] = s2 - s1

        self._delta_panel.update(dt, per_ch)


def open_full_run_window(source_file: str, parent=None) -> FullRunWindow | None:
    """Open a FullRunWindow for *source_file*. Returns None if no file given."""
    if not source_file:
        return None
    win = FullRunWindow(source_file=source_file, parent=parent)
    win.show()
    return win
