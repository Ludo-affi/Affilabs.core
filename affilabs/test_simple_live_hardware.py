"""Test simple acquisition with real hardware.
This bypasses all the complex calibration flow and just displays live data.
"""

import sys

import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# Import hardware and simple acquisition
sys.path.insert(0, "c:\\Users\\ludol\\ezControl-AI\\Affilabs.core beta")
from core.hardware_manager import HardwareManager
from core.simple_acquisition import SimpleAcquisitionManager


class SimpleLiveWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simple Live SPR - Real Hardware Test")
        self.resize(1200, 800)

        # Hardware
        self.hardware_mgr = HardwareManager()
        self.acq_mgr = SimpleAcquisitionManager(self.hardware_mgr)

        # Connect signal
        self.acq_mgr.spectrum_ready.connect(self.on_spectrum)

        # Spectrum counter
        self.spectrum_count = {"a": 0, "b": 0, "c": 0, "d": 0}

        # Setup UI
        self.setup_ui()

        # Connect hardware
        print("\n" + "=" * 70)
        print("Connecting to hardware...")
        print("=" * 70)
        self.connect_hardware()

    def setup_ui(self):
        """Build UI."""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Buttons
        btn_layout = QHBoxLayout()

        self.start_btn = QPushButton("Start Acquisition")
        self.start_btn.clicked.connect(self.start_acquisition)
        self.start_btn.setEnabled(False)
        btn_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Stop Acquisition")
        self.stop_btn.clicked.connect(self.stop_acquisition)
        self.stop_btn.setEnabled(False)
        btn_layout.addWidget(self.stop_btn)

        layout.addLayout(btn_layout)

        # Graphs - 2x2
        graph_container = QWidget()
        graph_layout = QVBoxLayout(graph_container)

        top_row = QHBoxLayout()
        self.plot_a = self.create_plot("Channel A", "#e74c3c")
        self.plot_b = self.create_plot("Channel B", "#3498db")
        top_row.addWidget(self.plot_a["widget"])
        top_row.addWidget(self.plot_b["widget"])
        graph_layout.addLayout(top_row)

        bottom_row = QHBoxLayout()
        self.plot_c = self.create_plot("Channel C", "#2ecc71")
        self.plot_d = self.create_plot("Channel D", "#f39c12")
        bottom_row.addWidget(self.plot_c["widget"])
        bottom_row.addWidget(self.plot_d["widget"])
        graph_layout.addLayout(bottom_row)

        layout.addWidget(graph_container)

        self.plots = {
            "a": self.plot_a,
            "b": self.plot_b,
            "c": self.plot_c,
            "d": self.plot_d,
        }

    def create_plot(self, title, color):
        """Create plot widget."""
        widget = pg.PlotWidget()
        widget.setBackground("w")
        widget.setTitle(title, color="k", size="12pt")
        widget.setLabel("left", "Transmission", units="AU")
        widget.setLabel("bottom", "Wavelength", units="nm")
        widget.showGrid(x=True, y=True, alpha=0.3)
        widget.setYRange(0, 1.2)

        curve = widget.plot(pen=pg.mkPen(color=color, width=2))

        return {"widget": widget, "curve": curve}

    def connect_hardware(self):
        """Connect to hardware and load fake calibration."""
        # Connect signal
        self.hardware_mgr.hardware_connected.connect(self.on_hardware_connected)

        # Start connection
        self.hardware_mgr.scan_and_connect()

    def on_hardware_connected(self, status):
        """Called when hardware connection completes."""
        try:
            if status.get("spectrometer"):
                print("Hardware connected!")

                # Load fake calibration data from a previous calibration
                # In real use, this would come from device config
                wavelengths = np.linspace(450, 850, 2048)
                dark = np.random.randn(len(wavelengths)) * 100 + 500

                # Fake S-ref (would normally come from calibration)
                s_ref = {
                    "a": np.random.randn(len(wavelengths)) * 1000 + 40000,
                    "b": np.random.randn(len(wavelengths)) * 1000 + 38000,
                    "c": np.random.randn(len(wavelengths)) * 1000 + 35000,
                    "d": np.random.randn(len(wavelengths)) * 1000 + 33000,
                }

                # LED intensities from calibration
                led_intensities = {"a": 255, "b": 150, "c": 150, "d": 255}

                # Set calibration data
                cal_data = {
                    "wavelengths": wavelengths,
                    "dark": dark,
                    "s_ref": s_ref,
                    "led_intensities": led_intensities,
                    "integration_time": 40,
                }

                self.acq_mgr.set_calibration_data(cal_data)

                print("Fake calibration loaded")
                print("Ready to start acquisition!")

                self.start_btn.setEnabled(True)
            else:
                print("ERROR: No hardware found!")

        except Exception as e:
            print(f"ERROR setting up calibration: {e}")
            import traceback

            traceback.print_exc()

    def start_acquisition(self):
        """Start acquisition."""
        print("\nStarting acquisition...")
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

        self.acq_mgr.start_acquisition()

    def stop_acquisition(self):
        """Stop acquisition."""
        print("\nStopping acquisition...")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

        self.acq_mgr.stop_acquisition()

        total = sum(self.spectrum_count.values())
        print(f"Total spectra acquired: {total}")

    def on_spectrum(self, data):
        """Handle spectrum data."""
        channel = data["channel"]
        wavelength = data["wavelength"]
        transmission = data["transmission"]

        if transmission is not None:
            # Update graph
            plot = self.plots[channel]
            plot["curve"].setData(wavelength, transmission)

            # Update count
            self.spectrum_count[channel] += 1

            # Update title
            total = sum(self.spectrum_count.values())
            plot["widget"].setTitle(
                f"Channel {channel.upper()} - {self.spectrum_count[channel]} spectra",
                color="k",
                size="11pt",
            )

    def closeEvent(self, event):
        """Clean shutdown."""
        if self.acq_mgr._acquiring:
            self.stop_acquisition()
        event.accept()


def main():
    print("=" * 70)
    print("Simple Live SPR - Real Hardware Test")
    print("=" * 70)
    print("This uses real hardware with minimal acquisition code")
    print("to prove the live data pipeline works.")
    print("=" * 70)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = SimpleLiveWindow()
    window.show()

    print("\nApplication ready!")
    print("Click 'Start Acquisition' to begin\n")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
