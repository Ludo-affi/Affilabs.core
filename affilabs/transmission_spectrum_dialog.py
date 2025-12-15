"""Transmission Spectrum Dialog - Shows the 4-channel transmission spectra
that get processed into each point on the live sensorgram.
"""

import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QVBoxLayout


class TransmissionSpectrumDialog(QDialog):
    """Dialog showing transmission spectra for all 4 channels."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Live Spectrum Viewer - Transmission & Raw Data")
        self.setMinimumSize(1200, 700)

        # Channel colors (matching main UI) - MUST be defined before _create_plot
        self.channel_colors = {
            "a": (255, 0, 0),  # Red
            "b": (0, 255, 0),  # Green
            "c": (0, 0, 255),  # Blue
            "d": (255, 165, 0),  # Orange
        }

        # Store latest data
        self.latest_wavelengths = None
        self.latest_transmission = {"a": None, "b": None, "c": None, "d": None}
        self.latest_raw_data = {"a": None, "b": None, "c": None, "d": None}
        self.reference_spectra = {}  # S-mode reference spectra from calibration

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Title
        title = QLabel("Live Spectrum Viewer")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(title)

        # Info label
        info = QLabel(
            "Real-time transmission and raw spectra for all channels. Each spectrum is processed to generate one point in the sensorgram.",
        )
        info.setStyleSheet("font-size: 11px; color: #666;")
        info.setWordWrap(True)
        layout.addWidget(info)

        # Create graphs container (side by side)
        from PySide6.QtWidgets import QWidget

        graphs_container = QWidget()
        graphs_layout = QHBoxLayout(graphs_container)
        graphs_layout.setContentsMargins(0, 0, 0, 0)
        graphs_layout.setSpacing(10)

        # Create the plots
        self._create_transmission_plot(graphs_layout)
        self._create_raw_data_plot(graphs_layout)

        layout.addWidget(graphs_container)

    def _create_transmission_plot(self, parent_layout):
        """Create the transmission spectrum plot."""
        # Create plot widget
        self.transmission_plot = pg.PlotWidget()
        self.transmission_plot.setBackground("w")
        self.transmission_plot.showGrid(x=True, y=True, alpha=0.3)

        # Configure axes
        self.transmission_plot.setLabel("left", "Transmission", units="%")
        self.transmission_plot.setLabel("bottom", "Wavelength", units="nm")
        self.transmission_plot.setTitle("Transmission Spectra (4 Channels)")

        # Prefer full auto-range; no hard axes (prevents clipping)
        try:
            self.transmission_plot.enableAutoRange(axis=pg.ViewBox.XYAxes, enable=True)
        except Exception:
            # Fallback if combined flag unsupported
            self.transmission_plot.enableAutoRange("x", True)
            self.transmission_plot.enableAutoRange("y", True)

        # Create curves for each channel
        self.transmission_curves = {}
        for channel in ["a", "b", "c", "d"]:
            color = self.channel_colors[channel]
            pen = pg.mkPen(color=color, width=2)
            curve = self.transmission_plot.plot(
                pen=pen,
                name=f"Channel {channel.upper()}",
            )
            self.transmission_curves[channel] = curve

        # Add legend
        self.transmission_plot.addLegend()

        parent_layout.addWidget(self.transmission_plot)

    def _create_raw_data_plot(self, parent_layout):
        """Create the raw data spectrum plot."""
        # Create plot widget
        self.raw_data_plot = pg.PlotWidget()
        self.raw_data_plot.setBackground("w")
        self.raw_data_plot.showGrid(x=True, y=True, alpha=0.3)

        # Configure axes
        self.raw_data_plot.setLabel("left", "Intensity", units="counts")
        self.raw_data_plot.setLabel("bottom", "Wavelength", units="nm")
        self.raw_data_plot.setTitle("Raw Data Spectra (4 Channels)")

        # Set axis ranges (detector wavelength range: 560-720 nm)
        self.raw_data_plot.setXRange(560, 720, padding=0.02)
        self.raw_data_plot.setYRange(0, 65535, padding=0.05)  # 16-bit range

        # Create curves for each channel (live P-mode data)
        self.raw_data_curves = {}
        for channel in ["a", "b", "c", "d"]:
            color = self.channel_colors[channel]
            pen = pg.mkPen(color=color, width=2)
            curve = self.raw_data_plot.plot(
                pen=pen,
                name=f"Ch {channel.upper()} (Live P-mode)",
            )
            self.raw_data_curves[channel] = curve

        # Create reference curves (S-mode reference from calibration)
        self.reference_curves = {}
        for channel in ["a", "b", "c", "d"]:
            color = self.channel_colors[channel]
            pen = pg.mkPen(
                color=color,
                width=1,
                style=pg.QtCore.Qt.DashLine,
            )  # Dashed line for reference
            curve = self.raw_data_plot.plot(
                pen=pen,
                name=f"Ch {channel.upper()} (S-ref)",
            )
            self.reference_curves[channel] = curve

        # Add legend
        self.raw_data_plot.addLegend()

        parent_layout.addWidget(self.raw_data_plot)

    def update_spectrum(
        self,
        channel: str,
        wavelengths: np.ndarray,
        transmission: np.ndarray,
        raw_data: np.ndarray = None,
    ):
        """Update transmission and raw data spectra for a specific channel.

        Args:
            channel: Channel letter ('a', 'b', 'c', 'd')
            wavelengths: Wavelength array in nm
            transmission: Transmission percentage array (0-100)
            raw_data: Raw intensity data (optional)

        """
        if channel not in self.transmission_curves:
            return

        # Store latest data
        self.latest_wavelengths = wavelengths
        self.latest_transmission[channel] = transmission
        if raw_data is not None:
            self.latest_raw_data[channel] = raw_data

        # Update the transmission curve
        if wavelengths is not None and transmission is not None:
            if len(wavelengths) == len(transmission):
                self.transmission_curves[channel].setData(wavelengths, transmission)

                # Dynamic autoscale to avoid clipping (keep floor at 0%)
                try:
                    # X-range from provided wavelengths with small padding
                    x_min = float(wavelengths[0])
                    x_max = float(wavelengths[-1])
                    if x_max > x_min:
                        pad = 0.02 * (x_max - x_min)
                        self.transmission_plot.setXRange(
                            x_min - pad,
                            x_max + pad,
                            padding=0,
                        )

                    # Y-range from current channel values; allow headroom to 10% over max
                    y_min = 0.0
                    y_max = (
                        float(np.nanmax(transmission)) if len(transmission) else 100.0
                    )
                    if not np.isfinite(y_max):
                        y_max = 100.0
                    y_max = max(100.0, y_max * 1.10)
                    # Clamp to a reasonable top to avoid runaway scale
                    y_max = min(y_max, 200.0)
                    self.transmission_plot.setYRange(y_min, y_max, padding=0.02)
                except Exception:
                    pass

        # Update the raw data curve
        if raw_data is not None and wavelengths is not None:
            if len(wavelengths) == len(raw_data):
                self.raw_data_curves[channel].setData(wavelengths, raw_data)

    def set_reference_spectra(self, ref_sig: dict, wavelengths: np.ndarray):
        """Set S-mode reference spectra from calibration.

        Args:
            ref_sig: Dictionary of reference spectra {channel: spectrum_array}
            wavelengths: Wavelength array corresponding to spectra

        """
        self.reference_spectra = ref_sig

        # Update reference curves
        if wavelengths is not None:
            for channel, ref_spectrum in ref_sig.items():
                if channel in self.reference_curves and ref_spectrum is not None:
                    if len(wavelengths) == len(ref_spectrum):
                        self.reference_curves[channel].setData(
                            wavelengths,
                            ref_spectrum,
                        )

    def clear_channel(self, channel: str):
        """Clear transmission and raw data spectra for a specific channel."""
        if channel in self.transmission_curves:
            self.transmission_curves[channel].clear()
            self.latest_transmission[channel] = None
        if channel in self.raw_data_curves:
            self.raw_data_curves[channel].clear()
            self.latest_raw_data[channel] = None

    def clear_all(self):
        """Clear all transmission and raw data spectra."""
        for channel in self.transmission_curves:
            self.transmission_curves[channel].clear()
            self.latest_transmission[channel] = None
        for channel in self.raw_data_curves:
            self.raw_data_curves[channel].clear()
            self.latest_raw_data[channel] = None
        self.latest_wavelengths = None
