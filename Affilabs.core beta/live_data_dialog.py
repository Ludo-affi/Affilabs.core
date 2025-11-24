"""Live Data Dialog - Side-by-side transmission and raw data graphs."""

from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt
import pyqtgraph as pg
import sys

# Disable PyQtGraph auto-cleanup to prevent shutdown crashes
pg.setConfigOption('exitCleanup', False)


class LiveDataDialog(QDialog):
    """Dialog showing live transmission and raw data graphs side by side."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Live Spectroscopy Data")
        self.resize(1400, 600)

        # Make dialog modeless (non-blocking)
        self.setModal(False)

        # Store curve references for each channel
        self.transmission_curves = {}  # {channel: curve}
        self.raw_data_curves = {}  # {channel: curve}

        # Setup and closing flags
        self._setup_complete = False
        self._is_closing = False

        try:
            self._setup_ui()
            self._setup_complete = True
        except Exception as e:
            if sys.stderr:
                print(f"Error setting up live data dialog: {e}")
                import traceback
                traceback.print_exc()

    def _setup_ui(self):
        """Setup the dialog UI with side-by-side graphs."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Title
        title = QLabel("Live Spectroscopy Data")
        title.setStyleSheet(
            "font-size: 20px;"
            "font-weight: 600;"
            "color: #1D1D1F;"
            "font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
        )
        layout.addWidget(title)

        # Graphs container
        graphs_layout = QHBoxLayout()
        graphs_layout.setSpacing(20)

        # Left: Transmission plot
        transmission_container = self._create_plot_container(
            "Transmission (%)",
            "transmission"
        )
        graphs_layout.addWidget(transmission_container)

        # Right: Raw data plot
        raw_data_container = self._create_plot_container(
            "Raw Intensity (counts)",
            "raw_data"
        )
        graphs_layout.addWidget(raw_data_container)

        layout.addLayout(graphs_layout)

    def _create_plot_container(self, title: str, plot_type: str):
        """Create a plot container with title and graph.

        Args:
            title: Plot title
            plot_type: 'transmission' or 'raw_data'
        """
        container = QFrame()
        container.setStyleSheet(
            "QFrame {"
            "  background: #FFFFFF;"
            "  border: 1px solid #D1D1D6;"
            "  border-radius: 8px;"
            "}"
        )

        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(12, 12, 12, 12)
        container_layout.setSpacing(8)

        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet(
            "font-size: 14px;"
            "font-weight: 600;"
            "color: #1D1D1F;"
            "background: transparent;"
            "border: none;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        container_layout.addWidget(title_label)

        # Channel indicators
        indicators_layout = QHBoxLayout()
        indicators_layout.setSpacing(12)

        channel_colors = {
            'a': '#FF3B30',  # Red
            'b': '#34C759',  # Green
            'c': '#007AFF',  # Blue
            'd': '#FF9500'   # Orange
        }

        for channel, color in channel_colors.items():
            indicator = QLabel(f"● Channel {channel.upper()}")
            indicator.setStyleSheet(
                f"font-size: 11px;"
                f"color: {color};"
                f"background: transparent;"
                f"border: none;"
                f"font-weight: 600;"
                f"font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            )
            indicators_layout.addWidget(indicator)

        indicators_layout.addStretch()
        container_layout.addLayout(indicators_layout)

        # Create plot widget
        plot_widget = pg.PlotWidget()
        plot_widget.setBackground('#FAFAFA')
        plot_widget.showGrid(x=True, y=True, alpha=0.2)

        # Disable mouse interaction to prevent crashes
        plot_widget.setMouseEnabled(x=False, y=False)
        plot_widget.setMenuEnabled(False)

        # Configure axes
        plot_widget.setLabel('bottom', 'Wavelength', units='nm')
        if plot_type == 'transmission':
            plot_widget.setLabel('left', 'Transmission', units='%')
            plot_widget.setYRange(0, 100)
        else:
            plot_widget.setLabel('left', 'Intensity', units='counts')
            plot_widget.setYRange(0, 65535)

        plot_widget.setXRange(400, 1000)

        # Create curves for each channel
        for channel, color in channel_colors.items():
            pen = pg.mkPen(color=color, width=2)
            curve = plot_widget.plot(pen=pen, name=f'Channel {channel.upper()}')

            if plot_type == 'transmission':
                self.transmission_curves[channel] = curve
            else:
                self.raw_data_curves[channel] = curve

        container_layout.addWidget(plot_widget)

        # Store plot widget reference
        if plot_type == 'transmission':
            self.transmission_plot = plot_widget
        else:
            self.raw_data_plot = plot_widget

        return container

    def update_transmission_plot(self, channel: str, wavelength, transmission_spectrum):
        """Update transmission plot with live data.

        Args:
            channel: Channel identifier ('a', 'b', 'c', 'd')
            wavelength: Wavelength array in nm
            transmission_spectrum: Transmission percentage array
        """
        if not self._setup_complete or self._is_closing:
            return

        if channel in self.transmission_curves:
            try:
                self.transmission_curves[channel].setData(wavelength, transmission_spectrum)
            except Exception:
                pass  # Silently ignore plotting errors

    def update_raw_data_plot(self, channel: str, wavelength, raw_spectrum):
        """Update raw data plot with live intensity data.

        Args:
            channel: Channel identifier ('a', 'b', 'c', 'd')
            wavelength: Wavelength array in nm
            raw_spectrum: Raw intensity array (counts)
        """
        if not self._setup_complete or self._is_closing:
            return

        if channel in self.raw_data_curves:
            try:
                self.raw_data_curves[channel].setData(wavelength, raw_spectrum)
            except Exception:
                pass  # Silently ignore plotting errors

    def closeEvent(self, event):
        """Handle dialog close event."""
        try:
            self._is_closing = True
            self._setup_complete = False

            # Clear all curves to prevent further updates
            self.transmission_curves.clear()
            self.raw_data_curves.clear()
        except:
            pass  # Swallow all exceptions during cleanup
        finally:
            try:
                super().closeEvent(event)
            except:
                pass  # Swallow exceptions from parent close

    def reject(self):
        """Handle dialog rejection (ESC key, close button)."""
        try:
            self._is_closing = True
            self._setup_complete = False
        except:
            pass  # Swallow all exceptions
        finally:
            try:
                super().reject()
            except:
                pass  # Swallow exceptions from parent reject
