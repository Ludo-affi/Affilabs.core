"""Simplified live data dialog - minimal processing to avoid crashes."""

import pyqtgraph as pg
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout


class SimpleLiveDialog(QDialog):
    """Simple dialog showing raw spectrum data with minimal processing."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Live Spectrum Data")
        self.resize(1400, 600)
        self.setModal(False)

        # Single curves for each channel (no separate transmission/raw - just raw data)
        self.curves = {}

        self._setup_ui()

    def _setup_ui(self):
        """Setup minimal UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel("Live Raw Spectrum Data")
        title.setStyleSheet("font-size: 18px; font-weight: 600; color: #1D1D1F;")
        layout.addWidget(title)

        # Single plot
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground("#FAFAFA")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.2)
        self.plot_widget.setLabel("bottom", "Wavelength", units="nm")
        self.plot_widget.setLabel("left", "Intensity", units="counts")

        # Disable mouse interaction
        self.plot_widget.setMouseEnabled(x=False, y=False)
        self.plot_widget.setMenuEnabled(False)

        # Create 4 curves
        colors = {"a": "#FF3B30", "b": "#34C759", "c": "#007AFF", "d": "#FF9500"}
        for channel, color in colors.items():
            pen = pg.mkPen(color=color, width=2)
            self.curves[channel] = self.plot_widget.plot(
                pen=pen,
                name=f"Ch {channel.upper()}",
            )

        layout.addWidget(self.plot_widget)

    def update_channel(self, channel: str, wavelength, intensity):
        """Update a channel with raw data - no processing.

        Args:
            channel: 'a', 'b', 'c', or 'd'
            wavelength: wavelength array
            intensity: raw intensity array

        """
        if channel in self.curves:
            try:
                self.curves[channel].setData(wavelength, intensity)
            except:
                pass  # Ignore any errors
