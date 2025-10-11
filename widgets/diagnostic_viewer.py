"""Real-time SPR Processing Diagnostics Viewer.

This widget displays all 4 processing steps in real-time as data flows through
the acquisition pipeline. No file I/O needed - uses direct signal emission.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox

try:
    import pyqtgraph as pg
except ImportError:
    pg = None

from utils.logger import logger


class DiagnosticViewer(QWidget):
    """Live 4-panel viewer showing SPR processing pipeline steps."""

    def __init__(self, parent=None):
        """Initialize the diagnostic viewer window."""
        super().__init__(parent)
        self.setWindowTitle("SPR Processing Diagnostics - Live View")
        self.resize(1400, 900)

        if pg is None:
            logger.error("pyqtgraph not installed - diagnostic viewer cannot display")
            return

        # Data storage for current frame
        self.current_data = {}
        self.paused = False

        # Setup UI
        self._setup_ui()

    def _setup_ui(self):
        """Create the UI layout with 4 plot panels."""
        layout = QVBoxLayout(self)

        # Control bar
        control_layout = QHBoxLayout()
        
        self.status_label = QLabel("Waiting for data...")
        self.status_label.setStyleSheet("font-weight: bold; color: #888;")
        control_layout.addWidget(self.status_label)
        
        control_layout.addStretch()
        
        self.pause_btn = QPushButton("⏸ Pause")
        self.pause_btn.clicked.connect(self._toggle_pause)
        control_layout.addWidget(self.pause_btn)
        
        self.highlight_spr_check = QCheckBox("Highlight SPR Range (580-720 nm)")
        self.highlight_spr_check.setChecked(True)
        self.highlight_spr_check.stateChanged.connect(self._update_all_plots)
        control_layout.addWidget(self.highlight_spr_check)
        
        layout.addLayout(control_layout)

        # Create 2x2 grid of plots
        grid_layout = QHBoxLayout()

        # Left column
        left_layout = QVBoxLayout()
        self.plot1 = self._create_plot("1. Raw Spectrum", "Counts", "blue")
        left_layout.addWidget(self.plot1['widget'])
        self.plot2 = self._create_plot("2. After Dark Correction", "Counts", "green")
        left_layout.addWidget(self.plot2['widget'])
        grid_layout.addLayout(left_layout)

        # Right column
        right_layout = QVBoxLayout()
        self.plot3 = self._create_plot("3. S-Reference (Corrected)", "Counts", "orange")
        right_layout.addWidget(self.plot3['widget'])
        self.plot4 = self._create_plot("4. Transmittance (Final)", "% Transmission", "red")
        right_layout.addWidget(self.plot4['widget'])
        grid_layout.addLayout(right_layout)

        layout.addLayout(grid_layout)

    def _create_plot(self, title: str, ylabel: str, color: str):
        """Create a single plot widget."""
        widget = pg.PlotWidget()
        widget.setBackground('w')
        widget.setTitle(title, color='k', size='12pt')
        widget.setLabel('left', ylabel, color='k')
        widget.setLabel('bottom', 'Wavelength (nm)', color='k')
        widget.showGrid(x=True, y=True, alpha=0.3)

        # Create plot curve
        pen = pg.mkPen(color=color, width=2)
        curve = widget.plot([], [], pen=pen)

        # Create SPR region indicator
        spr_region = pg.LinearRegionItem(
            [580, 720],
            brush=pg.mkBrush(0, 255, 0, 30),
            movable=False
        )
        widget.addItem(spr_region)
        spr_region.setVisible(self.highlight_spr_check.isChecked())

        # Stats text
        stats_text = pg.TextItem(anchor=(1, 0), color='k')
        widget.addItem(stats_text)

        return {
            'widget': widget,
            'curve': curve,
            'spr_region': spr_region,
            'stats_text': stats_text
        }

    @Slot(dict)
    def update_data(self, data: dict):
        """Update all plots with new processing data.
        
        Args:
            data: Dictionary containing:
                - channel: str
                - wavelengths: np.ndarray
                - raw: np.ndarray (raw spectrum)
                - dark_corrected: np.ndarray (after dark subtraction)
                - s_reference: np.ndarray (S-mode reference)
                - transmittance: np.ndarray (final P/S ratio)
        """
        if self.paused:
            return

        try:
            channel = data.get('channel', 'unknown')
            wavelengths = data.get('wavelengths')
            
            if wavelengths is None or len(wavelengths) == 0:
                return

            # Store current data
            self.current_data = data

            # Update status
            self.status_label.setText(f"Channel {channel.upper()} - {len(wavelengths)} pixels")
            self.status_label.setStyleSheet("font-weight: bold; color: green;")

            # Update each plot
            self._update_plot(self.plot1, wavelengths, data.get('raw'))
            self._update_plot(self.plot2, wavelengths, data.get('dark_corrected'))
            self._update_plot(self.plot3, wavelengths, data.get('s_reference'))
            self._update_plot(self.plot4, wavelengths, data.get('transmittance'))

        except Exception as e:
            logger.error(f"Failed to update diagnostic viewer: {e}")

    def _update_plot(self, plot_dict: dict, wavelengths: np.ndarray, spectrum: np.ndarray):
        """Update a single plot with data."""
        if spectrum is None or wavelengths is None:
            return

        try:
            # Handle size mismatch
            if len(wavelengths) != len(spectrum):
                min_len = min(len(wavelengths), len(spectrum))
                wavelengths = wavelengths[:min_len]
                spectrum = spectrum[:min_len]

            # Update curve
            plot_dict['curve'].setData(wavelengths, spectrum)

            # Update statistics
            mean_val = np.mean(spectrum)
            max_val = np.max(spectrum)
            min_val = np.min(spectrum)
            std_val = np.std(spectrum)

            stats_text = f"Mean: {mean_val:.1f}\nMax: {max_val:.1f}\nMin: {min_val:.1f}\nStd: {std_val:.2f}"
            plot_dict['stats_text'].setText(stats_text)
            plot_dict['stats_text'].setPos(wavelengths[-1], max_val)

        except Exception as e:
            logger.warning(f"Failed to update plot: {e}")

    def _toggle_pause(self):
        """Toggle pause/resume of updates."""
        self.paused = not self.paused
        if self.paused:
            self.pause_btn.setText("▶ Resume")
            self.status_label.setText("⏸ PAUSED")
            self.status_label.setStyleSheet("font-weight: bold; color: orange;")
        else:
            self.pause_btn.setText("⏸ Pause")
            self.status_label.setStyleSheet("font-weight: bold; color: green;")

    def _update_all_plots(self):
        """Update SPR region visibility on all plots."""
        show_spr = self.highlight_spr_check.isChecked()
        for plot in [self.plot1, self.plot2, self.plot3, self.plot4]:
            plot['spr_region'].setVisible(show_spr)

    def closeEvent(self, event):
        """Handle window close."""
        logger.info("Diagnostic viewer closed")
        event.accept()
