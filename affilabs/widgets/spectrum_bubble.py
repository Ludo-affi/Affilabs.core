"""SpectrumBubble — floating spectroscopy overlay panel.

A frameless child widget positioned over the main window bottom-left corner.
Zero layout impact: no splitter space consumed, available on every tab.
Toggle with toggle(). Repositions on parent resize via reposition().

Structure:
    Header (drag handle + title + close)
    Tab row  — "Transmission" | "Raw"  (pill buttons)
    QStackedWidget — one pyqtgraph plot per tab  (220 px each)
    Baseline capture button
"""

import logging

from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QWidget, QGraphicsDropShadowEffect,
)
from PySide6.QtGui import QColor

logger = logging.getLogger(__name__)

_BUBBLE_W = 310
_BUBBLE_H = 380
_MARGIN_LEFT = 16
_MARGIN_BOTTOM = 52   # clears the transport bar

_BG      = "#FFFFFF"
_HDR_BG  = "#F5F5F7"
_BORDER  = "#E5E5EA"
_TEXT    = "#1D1D1F"
_MUTED   = "#86868B"
_ACCENT  = "#2E30E3"
_ACCENT_LIGHT = "rgba(46,48,227,0.09)"

# Legacy aliases used inside _build_* methods
_DARK_BG     = _BG
_DARK_HDR    = _HDR_BG
_DARK_BORDER = _BORDER
_DARK_TEXT   = _TEXT
_DARK_MUTED  = _MUTED


class SpectrumBubble(QFrame):
    """Floating spectroscopy view panel. Parented to main window, overlaid above content.

    Public attributes (aliased to main_window after creation):
        transmission_plot   pyqtgraph PlotWidget — Transmission trace
        transmission_curves list[PlotDataItem]   — 4 channel curves
        raw_data_plot       pyqtgraph PlotWidget — Raw counts trace
        raw_data_curves     list[PlotDataItem]   — 4 channel curves
        baseline_capture_btn QPushButton

    Usage::
        bubble = SpectrumBubble(main_window)
        bubble.toggle()       # open / close
        bubble.reposition()   # call from parent resizeEvent
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SpectrumBubble")
        self.setFixedSize(_BUBBLE_W, _BUBBLE_H)
        self._drag_offset = QPoint()

        # Public plot attributes — set in _build_plots()
        self.transmission_plot = None
        self.transmission_curves: list = []
        self.raw_data_plot = None
        self.raw_data_curves: list = []
        self.baseline_capture_btn: QPushButton | None = None

        self._tab_btns: list[QPushButton] = []
        self._stack: QStackedWidget | None = None

        try:
            self._setup_ui()
        except Exception as e:
            logger.error(f"SpectrumBubble setup failed (non-fatal): {e}", exc_info=True)

        self.hide()

    # ──────────────────────────────────────────────────────────────────────
    # UI construction
    # ──────────────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            QFrame#SpectrumBubble {{
                background: {_BG};
                border-radius: 14px;
                border: 1px solid {_BORDER};
            }}
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(32)
        shadow.setColor(QColor(0, 0, 0, 55))
        shadow.setOffset(0, 6)
        self.setGraphicsEffect(shadow)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        outer.addWidget(self._build_header())
        outer.addWidget(self._build_tab_row())

        self._stack = QStackedWidget()
        self._stack.setStyleSheet("QStackedWidget { background: transparent; border: none; }")
        self._build_plots()
        outer.addWidget(self._stack, 1)

        outer.addWidget(self._build_baseline_section())

        # Drag support via header
        self._header.mousePressEvent = self._on_header_press
        self._header.mouseMoveEvent = self._on_header_move

        # Start on Transmission tab
        self._switch_tab(0)

    def _build_header(self) -> QFrame:
        hdr = QFrame()
        hdr.setFixedHeight(44)
        hdr.setStyleSheet(f"""
            QFrame {{
                background: {_HDR_BG};
                border-radius: 14px 14px 0px 0px;
                border-bottom: 1px solid {_BORDER};
            }}
        """)
        hdr.setCursor(Qt.CursorShape.SizeAllCursor)
        self._header = hdr

        row = QHBoxLayout(hdr)
        row.setContentsMargins(14, 0, 10, 0)
        row.setSpacing(8)

        title = QLabel("Spectrum")
        title.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {_TEXT};"
            " background: transparent; border: none; border-radius: 0px;"
        )
        row.addWidget(title)
        row.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {_MUTED};
                font-size: 13px;
                font-weight: 500;
                border-radius: 12px;
            }}
            QPushButton:hover {{ background: {_BORDER}; color: {_TEXT}; }}
        """)
        close_btn.clicked.connect(self._close_and_uncheck)
        row.addWidget(close_btn)

        return hdr

    def _build_tab_row(self) -> QWidget:
        wrap = QWidget()
        wrap.setStyleSheet(f"background: {_BG}; border: none;")
        layout = QHBoxLayout(wrap)
        layout.setContentsMargins(12, 8, 12, 4)
        layout.setSpacing(5)

        for i, label in enumerate(("Transmission", "Raw")):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedHeight(26)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(self._tab_inactive_style())
            self._tab_btns.append(btn)
            layout.addWidget(btn)
            idx = i
            btn.clicked.connect(lambda _checked, ix=idx: self._switch_tab(ix))

        layout.addStretch()
        return wrap

    def _build_plots(self) -> None:
        try:
            from plot_helpers import add_channel_curves, create_spectroscopy_plot
        except ImportError:
            logger.error("SpectrumBubble: plot_helpers not importable — plots disabled")
            return

        # ── Transmission page ──────────────────────────────────────────────
        trans_page = QWidget()
        trans_page.setStyleSheet("background: transparent;")
        trans_layout = QVBoxLayout(trans_page)
        trans_layout.setContentsMargins(8, 2, 8, 0)
        trans_layout.setSpacing(0)

        self.transmission_plot = create_spectroscopy_plot(
            left_label="Transmission (norm.)",
            bottom_label="Wavelength (nm)",
        )
        self.transmission_curves = add_channel_curves(self.transmission_plot)
        trans_layout.addWidget(self.transmission_plot)
        self._stack.addWidget(trans_page)

        # ── Raw page ───────────────────────────────────────────────────────
        raw_page = QWidget()
        raw_page.setStyleSheet("background: transparent;")
        raw_layout = QVBoxLayout(raw_page)
        raw_layout.setContentsMargins(8, 2, 8, 0)
        raw_layout.setSpacing(0)

        self.raw_data_plot = create_spectroscopy_plot(
            left_label="Intensity (counts)",
            bottom_label="Wavelength (nm)",
        )
        self.raw_data_curves = add_channel_curves(self.raw_data_plot)
        raw_layout.addWidget(self.raw_data_plot)
        self._stack.addWidget(raw_page)

    def _build_baseline_section(self) -> QWidget:
        wrap = QWidget()
        wrap.setStyleSheet(f"background: {_BG}; border: none;")
        layout = QHBoxLayout(wrap)
        layout.setContentsMargins(12, 6, 12, 12)
        layout.setSpacing(0)

        self.baseline_capture_btn = QPushButton("Capture 5-Min Baseline")
        self.baseline_capture_btn.setObjectName("spec_baseline_btn")
        self.baseline_capture_btn.setFixedHeight(28)
        self.baseline_capture_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.baseline_capture_btn.setStyleSheet(f"""
            QPushButton#spec_baseline_btn {{
                background-color: {_HDR_BG};
                color: {_MUTED};
                border: 1px solid {_BORDER};
                border-radius: 7px;
                padding: 3px 10px;
                font-size: 11px;
                font-weight: 500;
                font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;
            }}
            QPushButton#spec_baseline_btn:hover {{
                background-color: {_BORDER};
                color: {_TEXT};
                border-color: #C5C5CA;
            }}
            QPushButton#spec_baseline_btn:pressed {{ background-color: #D5D5DA; }}
            QPushButton#spec_baseline_btn:disabled {{ color: #C7C7CC; border-color: {_HDR_BG}; }}
        """)
        self.baseline_capture_btn.setToolTip(
            "Capture 5 minutes of baseline transmission data\n"
            "for noise analysis and drift measurement.\n\n"
            "Requirements:\n"
            "• Stable baseline (no injections)\n"
            "• Live acquisition running\n"
            "• System calibrated"
        )
        layout.addWidget(self.baseline_capture_btn)
        return wrap

    # ──────────────────────────────────────────────────────────────────────
    # Tab switching
    # ──────────────────────────────────────────────────────────────────────

    def _switch_tab(self, index: int) -> None:
        if self._stack is not None:
            self._stack.setCurrentIndex(index)
        for i, btn in enumerate(self._tab_btns):
            active = (i == index)
            btn.setChecked(active)
            btn.setStyleSheet(self._tab_active_style() if active else self._tab_inactive_style())

    @staticmethod
    def _tab_inactive_style() -> str:
        return (
            f"QPushButton {{"
            f"  background: {_HDR_BG};"
            f"  color: {_MUTED};"
            f"  border: 1px solid {_BORDER};"
            f"  border-radius: 6px;"
            f"  padding: 2px 10px;"
            f"  font-size: 11px;"
            f"  font-weight: 500;"
            f"  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            f"}}"
            f"QPushButton:hover {{ background: {_BORDER}; color: {_TEXT}; }}"
        )

    @staticmethod
    def _tab_active_style() -> str:
        return (
            f"QPushButton {{"
            f"  background: {_ACCENT};"
            f"  color: #FFFFFF;"
            f"  border: 1px solid {_ACCENT};"
            f"  border-radius: 6px;"
            f"  padding: 2px 10px;"
            f"  font-size: 11px;"
            f"  font-weight: 600;"
            f"  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            f"}}"
        )

    # ──────────────────────────────────────────────────────────────────────
    # Drag
    # ──────────────────────────────────────────────────────────────────────

    def _on_header_press(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )

    def _on_header_move(self, event) -> None:
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)

    # ──────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────

    def toggle(self) -> None:
        """Show or hide. On show: repositions and raises to front."""
        if self.isVisible():
            self.hide()
        else:
            self.reposition()
            self.show()
            self.raise_()

    def reposition(self) -> None:
        """Snap to bottom-left of parent, above the nav bar area."""
        p = self.parent()
        if p is None:
            return
        self.move(_MARGIN_LEFT, p.height() - _BUBBLE_H - _MARGIN_BOTTOM)

    def _close_and_uncheck(self) -> None:
        self.hide()
        p = self.parent()
        if p is not None:
            btn = getattr(p, "spectrum_toggle_btn", None)
            if btn is not None:
                btn.setChecked(False)
