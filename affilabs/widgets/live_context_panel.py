"""Live Context Panel — Spectroscopy plots alongside the sensorgram.

Phase 3 of sidebar redesign (v2.1).
Moves transmission + raw spectroscopy plots from the Settings sidebar into
the main sensorgram view so they're visible during live acquisition.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class LiveContextPanel(QFrame):
    """Narrow left panel for the Live page: transmission + raw spectroscopy plots.

    Attributes:
        transmission_plot:   pyqtgraph PlotWidget for transmission spectrum
        raw_data_plot:       pyqtgraph PlotWidget for raw detector counts
        transmission_curves: list of 4 PlotDataItems (channels A–D)
        raw_data_curves:     list of 4 PlotDataItems (channels A–D)
        baseline_capture_btn: QPushButton for 5-min baseline capture
    """

    WIDTH = 230  # Fixed panel width in pixels

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("LiveContextPanel")
        self.setFixedWidth(self.WIDTH)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(
            "QFrame#LiveContextPanel {"
            "  background: #F8F9FA;"
            "  border-right: 1px solid #D5D5D7;"
            "}"
        )

        # Placeholder attributes (populated by _build_plots)
        self.transmission_plot = None
        self.raw_data_plot = None
        self.transmission_curves = []
        self.raw_data_curves = []
        self.baseline_capture_btn = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        self._build_header(layout)
        self._build_plots(layout)
        layout.addStretch(1)

    # ─────────────────────────────────────────────────────────────────────
    # Internal builders
    # ─────────────────────────────────────────────────────────────────────

    def _build_header(self, layout: QVBoxLayout) -> None:
        """Header row: 'Spectroscopy' label."""
        header = QLabel("SPECTROSCOPY")
        header.setStyleSheet(
            "QLabel {"
            "  font-size: 10px;"
            "  font-weight: 700;"
            "  color: #86868B;"
            "  letter-spacing: 0.5px;"
            "  background: transparent;"
            "  margin-bottom: 4px;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        layout.addWidget(header)

    def _build_plots(self, layout: QVBoxLayout) -> None:
        """Build transmission and raw data spectroscopy plots."""
        from plot_helpers import add_channel_curves, create_spectroscopy_plot

        # ── Transmission plot ──────────────────────────────────────────
        trans_label = QLabel("Transmission (%):")
        trans_label.setStyleSheet(self._plot_label_style())
        layout.addWidget(trans_label)

        self.transmission_plot = create_spectroscopy_plot(
            left_label="Transmission (norm.)",
            bottom_label="Wavelength (nm)",
        )
        self.transmission_plot.setFixedHeight(160)
        layout.addWidget(self.transmission_plot)

        self.transmission_curves = add_channel_curves(self.transmission_plot)

        # ── Capture Baseline button ───────────────────────────────────
        self.baseline_capture_btn = QPushButton("[REC] Capture 5-Min Baseline")
        self.baseline_capture_btn.setObjectName("baseline_capture_btn")
        self.baseline_capture_btn.setFixedHeight(26)
        self.baseline_capture_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.baseline_capture_btn.setStyleSheet(
            "QPushButton#baseline_capture_btn {"
            "  background-color: #F2F2F7;"
            "  color: #666666;"
            "  border: 1px solid #E5E5EA;"
            "  border-radius: 6px;"
            "  padding: 3px 8px;"
            "  font-size: 10px;"
            "  font-weight: normal;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton#baseline_capture_btn:hover { background-color: #E8E8ED; border: 1px solid #D5D5DA; }"
            "QPushButton#baseline_capture_btn:pressed { background-color: #DADADF; }"
            "QPushButton#baseline_capture_btn:disabled { color: #C7C7CC; }"
        )
        self.baseline_capture_btn.setToolTip(
            "Capture 5 minutes of baseline transmission data\n"
            "for noise analysis and optimization.\n\n"
            "Requirements:\n"
            "• Stable baseline (no injections)\n"
            "• Live acquisition running\n"
            "• System calibrated"
        )
        layout.addWidget(self.baseline_capture_btn)

        layout.addSpacing(8)

        # ── Raw data plot ──────────────────────────────────────────────
        raw_label = QLabel("Raw Signal (counts):")
        raw_label.setStyleSheet(self._plot_label_style())
        layout.addWidget(raw_label)

        self.raw_data_plot = create_spectroscopy_plot(
            left_label="Intensity (counts)",
            bottom_label="Wavelength (nm)",
        )
        self.raw_data_plot.setFixedHeight(160)
        layout.addWidget(self.raw_data_plot)

        self.raw_data_curves = add_channel_curves(self.raw_data_plot)

    # ─────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def _plot_label_style() -> str:
        return (
            "font-size: 11px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-weight: 500;"
            "margin-bottom: 2px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
