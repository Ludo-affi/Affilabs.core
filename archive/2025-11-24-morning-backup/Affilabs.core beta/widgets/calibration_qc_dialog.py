"""Calibration QC Dialog - Displays 5 comprehensive graphs for quality control.

Shows:
1. S-pol final spectra (all 4 channels)
2. P-pol final spectra (all 4 channels)
3. Final dark scan (all 4 channels)
4. Final afterglow simulation curves (all 4 channels)
5. Transmission spectra (all 4 channels)
"""

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QGridLayout, QFrame
)
import pyqtgraph as pg
from utils.logger import logger


class CalibrationQCDialog(QDialog):
    """Dialog showing calibration QC graphs."""

    def __init__(self, parent=None, calibration_data: dict = None):
        """Initialize the QC dialog.

        Args:
            parent: Parent widget
            calibration_data: Dictionary containing all calibration results:
                - s_pol_spectra: dict of {channel: spectrum_array}
                - p_pol_spectra: dict of {channel: spectrum_array}
                - dark_scan: dict of {channel: dark_array}
                - afterglow_curves: dict of {channel: afterglow_array}
                - transmission_spectra: dict of {channel: transmission_array}
                - wavelengths: array of wavelength values
                - integration_time: float (ms)
                - led_intensities: dict of {channel: intensity}
        """
        super().__init__(parent)
        self.calibration_data = calibration_data or {}

        self.setWindowTitle("Calibration QC Report")
        self.setMinimumSize(1400, 900)
        self.setModal(True)

        # Apply modern styling
        self.setStyleSheet("""
            QDialog {
                background: #FFFFFF;
            }
            QLabel {
                color: #1D1D1F;
                font-size: 13px;
            }
            QPushButton {
                background: #007AFF;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: 600;
                min-width: 100px;
            }
            QPushButton:hover {
                background: #0051D5;
            }
            QPushButton:pressed {
                background: #003D99;
            }
        """)

        self._setup_ui()

    def _setup_ui(self):
        """Setup the UI layout with 5 graphs."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Title
        title = QLabel("📊 Calibration Quality Control Report")
        title.setStyleSheet("""
            font-size: 20px;
            font-weight: 600;
            color: #1D1D1F;
            padding: 10px 0px;
        """)
        layout.addWidget(title)

        # Summary info
        summary = self._create_summary_section()
        layout.addWidget(summary)

        # Grid of graphs (2x3 layout - 5 graphs + 1 empty)
        graphs_container = QFrame()
        graphs_layout = QGridLayout(graphs_container)
        graphs_layout.setSpacing(15)

        # Row 1: S-pol and P-pol
        s_pol_graph = self._create_graph("1. S-Polarization Final Spectra", "s_pol")
        p_pol_graph = self._create_graph("2. P-Polarization Final Spectra", "p_pol")
        graphs_layout.addWidget(s_pol_graph, 0, 0)
        graphs_layout.addWidget(p_pol_graph, 0, 1)

        # Row 2: Dark and Afterglow
        dark_graph = self._create_graph("3. Final Dark Scan", "dark")
        afterglow_graph = self._create_graph("4. Afterglow Simulation Curves", "afterglow")
        graphs_layout.addWidget(dark_graph, 1, 0)
        graphs_layout.addWidget(afterglow_graph, 1, 1)

        # Row 3: Transmission (spans both columns)
        transmission_graph = self._create_graph("5. Transmission Spectra", "transmission")
        graphs_layout.addWidget(transmission_graph, 2, 0, 1, 2)  # Span 2 columns

        layout.addWidget(graphs_container)

        # Close button
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def _create_summary_section(self) -> QLabel:
        """Create summary information section."""
        data = self.calibration_data

        integration_time = data.get('integration_time', 0)
        led_intensities = data.get('led_intensities', {})

        led_str = ", ".join([f"Ch {ch.upper()}: {led_intensities.get(ch, 0)}" for ch in ['a', 'b', 'c', 'd']])

        summary_text = (
            f"<b>Integration Time:</b> {integration_time:.2f} ms  |  "
            f"<b>LED Intensities:</b> {led_str}"
        )

        summary_label = QLabel(summary_text)
        summary_label.setTextFormat(Qt.TextFormat.RichText)
        summary_label.setStyleSheet("""
            background: #F5F5F7;
            padding: 12px 16px;
            border-radius: 8px;
            font-size: 12px;
            color: #1D1D1F;
        """)

        return summary_label

    def _create_graph(self, title: str, data_type: str) -> QFrame:
        """Create a single graph widget.

        Args:
            title: Graph title
            data_type: Type of data ('s_pol', 'p_pol', 'dark', 'afterglow', 'transmission')

        Returns:
            QFrame containing the graph
        """
        container = QFrame()
        container.setFrameShape(QFrame.Shape.StyledPanel)
        container.setStyleSheet("""
            QFrame {
                background: #FFFFFF;
                border: 1px solid #D1D1D6;
                border-radius: 8px;
            }
        """)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)

        # Title label
        title_label = QLabel(title)
        title_label.setStyleSheet("""
            font-size: 14px;
            font-weight: 600;
            color: #1D1D1F;
            padding: 5px 0px;
        """)
        layout.addWidget(title_label)

        # Create plot widget
        plot_widget = pg.PlotWidget()
        plot_widget.setBackground('w')
        plot_widget.showGrid(x=True, y=True, alpha=0.3)

        # Configure axes
        plot_widget.setLabel('bottom', 'Wavelength', units='nm')

        if data_type == 'transmission':
            plot_widget.setLabel('left', 'Transmission', units='%')
        elif data_type == 'afterglow':
            plot_widget.setLabel('left', 'Afterglow Correction', units='counts')
        else:
            plot_widget.setLabel('left', 'Intensity', units='counts')

        # Plot data
        self._plot_data(plot_widget, data_type)

        layout.addWidget(plot_widget)

        return container

    def _plot_data(self, plot_widget: pg.PlotWidget, data_type: str):
        """Plot data on the graph widget.

        Args:
            plot_widget: PyQtGraph PlotWidget
            data_type: Type of data to plot
        """
        data = self.calibration_data
        wavelengths = data.get('wavelengths', None)

        if wavelengths is None:
            wavelengths = np.linspace(560, 720, 3648)  # Default wavelength array
            logger.warning(f"No wavelengths in QC data, using default range")

        # Channel colors (matching existing UI)
        colors = {
            'a': (255, 0, 0, 200),      # Red
            'b': (0, 255, 0, 200),      # Green
            'c': (0, 0, 255, 200),      # Blue
            'd': (255, 165, 0, 200)     # Orange
        }

        # Get data based on type
        data_dict = {}
        if data_type == 's_pol':
            data_dict = data.get('s_pol_spectra', {})
        elif data_type == 'p_pol':
            data_dict = data.get('p_pol_spectra', {})
        elif data_type == 'dark':
            data_dict = data.get('dark_scan', {})
        elif data_type == 'afterglow':
            data_dict = data.get('afterglow_curves', {})
        elif data_type == 'transmission':
            data_dict = data.get('transmission_spectra', {})

        # Plot each channel
        for channel in ['a', 'b', 'c', 'd']:
            if channel in data_dict:
                spectrum = data_dict[channel]
                if spectrum is not None and len(spectrum) > 0:
                    # Handle wavelength array length mismatch
                    if len(wavelengths) != len(spectrum):
                        wavelengths_plot = np.linspace(wavelengths[0], wavelengths[-1], len(spectrum))
                    else:
                        wavelengths_plot = wavelengths

                    pen = pg.mkPen(color=colors.get(channel, (128, 128, 128, 200)), width=2)
                    plot_widget.plot(
                        wavelengths_plot,
                        spectrum,
                        pen=pen,
                        name=f"Channel {channel.upper()}"
                    )

        # Add legend
        plot_widget.addLegend(offset=(10, 10))

    @staticmethod
    def show_qc_report(parent=None, calibration_data: dict = None):
        """Static method to show QC report dialog.

        Args:
            parent: Parent widget
            calibration_data: Calibration data dictionary

        Returns:
            Dialog result (QDialog.Accepted or QDialog.Rejected)
        """
        dialog = CalibrationQCDialog(parent=parent, calibration_data=calibration_data)

        # Ensure dialog is visible and comes to front
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

        return dialog.exec()
