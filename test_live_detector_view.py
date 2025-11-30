"""
Test UI for Live Detector Output Monitoring

Shows real-time detector output with:
- Live spectrum display for all 4 channels
- Integration time control
- LED intensity control per channel
- Polarizer position control (S/P mode switching)
- Max counts and saturation monitoring
"""

import sys
import numpy as np
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSpinBox, QGroupBox, QTextEdit, QSplitter,
    QTabWidget, QSlider, QComboBox
)
from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtGui import QFont
import pyqtgraph as pg

# Add project paths
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from utils.device_configuration import DeviceConfiguration
from utils.logger import logger
from core.hardware_manager import HardwareManager


class LiveDetectorMonitor(QMainWindow):
    """Test UI for live detector monitoring"""

    def __init__(self):
        super().__init__()

        self.hardware_mgr = None
        self.hardware_ready = False
        self.device_config = None

        # Acquisition settings
        self.integration_time = 50.0  # ms
        self.led_intensities = {'a': 0, 'b': 0, 'c': 0, 'd': 0}
        self.current_mode = 's'  # s or p

        # Live acquisition
        self.acquisition_timer = QTimer()
        self.acquisition_timer.timeout.connect(self._acquire_spectrum)
        self.is_acquiring = False

        self._setup_ui()
        self._connect_hardware()

    def _setup_ui(self):
        """Setup the user interface"""
        self.setWindowTitle("Live Detector Monitor")
        self.resize(1600, 900)

        # Main widget
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # Top controls
        controls_layout = QHBoxLayout()
        main_layout.addLayout(controls_layout)

        # Hardware status
        status_group = QGroupBox("Hardware Status")
        status_layout = QVBoxLayout(status_group)
        self.status_label = QLabel("Initializing...")
        self.status_label.setFont(QFont("Consolas", 10))
        status_layout.addWidget(self.status_label)
        controls_layout.addWidget(status_group)

        # Acquisition controls
        acq_group = QGroupBox("Acquisition Control")
        acq_layout = QVBoxLayout(acq_group)

        # Integration time
        int_layout = QHBoxLayout()
        int_layout.addWidget(QLabel("Integration Time (ms):"))
        self.int_spin = QSpinBox()
        self.int_spin.setRange(1, 1000)
        self.int_spin.setValue(50)
        self.int_spin.valueChanged.connect(self._update_integration_time)
        int_layout.addWidget(self.int_spin)
        acq_layout.addLayout(int_layout)

        # Polarizer mode
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Polarizer Mode:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(['S-Mode', 'P-Mode'])
        self.mode_combo.currentIndexChanged.connect(self._update_polarizer_mode)
        mode_layout.addWidget(self.mode_combo)
        acq_layout.addLayout(mode_layout)

        # Start/Stop buttons
        self.start_button = QPushButton("Start Live View")
        self.start_button.setEnabled(False)
        self.start_button.clicked.connect(self._start_acquisition)
        acq_layout.addWidget(self.start_button)

        self.stop_button = QPushButton("Stop Live View")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._stop_acquisition)
        acq_layout.addWidget(self.stop_button)

        controls_layout.addWidget(acq_group)

        # LED controls
        led_group = QGroupBox("LED Intensities (0-255)")
        led_layout = QVBoxLayout(led_group)

        self.led_sliders = {}
        self.led_labels = {}
        for ch in ['a', 'b', 'c', 'd']:
            ch_layout = QHBoxLayout()
            ch_layout.addWidget(QLabel(f"LED {ch.upper()}:"))

            slider = QSlider(Qt.Horizontal)
            slider.setRange(0, 255)
            slider.setValue(0)
            slider.valueChanged.connect(lambda v, c=ch: self._update_led_intensity(c, v))
            self.led_sliders[ch] = slider
            ch_layout.addWidget(slider)

            label = QLabel("0")
            label.setMinimumWidth(30)
            self.led_labels[ch] = label
            ch_layout.addWidget(label)

            led_layout.addLayout(ch_layout)

        controls_layout.addWidget(led_group)
        controls_layout.addStretch()

        # Plot tabs
        self.plot_tabs = QTabWidget()
        main_layout.addWidget(self.plot_tabs, stretch=1)

        # Create plot widgets for each channel
        self.channel_plots = {}
        self.channel_curves = {}

        for ch in ['a', 'b', 'c', 'd']:
            plot_widget = pg.PlotWidget(title=f"Channel {ch.upper()} - Live Spectrum")
            plot_widget.setLabel('left', 'Intensity', units='counts')
            plot_widget.setLabel('bottom', 'Wavelength', units='nm')
            plot_widget.showGrid(x=True, y=True, alpha=0.3)
            plot_widget.setBackground('w')
            plot_widget.setYRange(0, 70000)

            # Add spectrum curve
            curve = plot_widget.plot(pen=pg.mkPen(color='b', width=2))
            self.channel_curves[ch] = curve

            # Add saturation line
            saturation_line = pg.InfiniteLine(
                pos=62258,
                angle=0,
                pen=pg.mkPen(color='r', width=2, style=Qt.DashLine),
                label='Saturation (95%)',
                labelOpts={'position': 0.95}
            )
            plot_widget.addItem(saturation_line)

            # Add max counts label
            text_item = pg.TextItem(
                text="Max: 0",
                anchor=(1, 0),
                color=(0, 0, 0)
            )
            text_item.setPos(800, 60000)
            plot_widget.addItem(text_item)

            self.channel_plots[ch] = {
                'widget': plot_widget,
                'text': text_item
            }

            self.plot_tabs.addTab(plot_widget, f"Channel {ch.upper()}")

        # Log output
        log_group = QGroupBox("Status Log")
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setMaximumHeight(150)
        log_layout.addWidget(self.log_text)
        main_layout.addWidget(log_group)

    def _connect_hardware(self):
        """Initialize hardware connections"""
        try:
            self._log("Initializing hardware...")

            # Load device config
            config_path = Path(__file__).parent / "device_config.json"
            self.device_config = DeviceConfiguration(str(config_path))
            self._log(f"Device config loaded: {config_path}")

            # Initialize hardware manager
            self._log("Scanning for hardware...")
            self.hardware_mgr = HardwareManager()

            def on_progress(msg):
                self._log(msg)

            def on_connected(info):
                self._log(f"Hardware connected: {info}")

                # Store references
                self.controller = self.hardware_mgr.ctrl
                self.usb = self.hardware_mgr.usb

                if not self.controller or not self.usb:
                    self._log("ERROR: Controller or spectrometer missing!")
                    return

                # Get servo positions
                servo_positions = self.device_config.get_servo_positions()
                s_pos = servo_positions['s']
                p_pos = servo_positions['p']
                self._log(f"Servo positions: S={s_pos}°, P={p_pos}°")

                # Update status
                ctrl_name = info.get('ctrl_type', 'Unknown')
                spec_name = info.get('spectrometer', 'Unknown')
                self.status_label.setText(
                    f"✓ Controller: {ctrl_name}\n"
                    f"✓ Detector: {spec_name}\n"
                    f"✓ Servo: S={s_pos}° P={p_pos}°"
                )
                self.status_label.setStyleSheet("color: green;")

                self.hardware_ready = True
                self.start_button.setEnabled(True)
                self._log("Hardware ready! Set LED intensities and click Start Live View")

            def on_error(error_msg):
                self._log(f"Hardware error: {error_msg}")
                self.status_label.setText(f"✗ {error_msg}")
                self.status_label.setStyleSheet("color: red;")

            self.hardware_mgr.connection_progress.connect(on_progress)
            self.hardware_mgr.hardware_connected.connect(on_connected)
            self.hardware_mgr.error_occurred.connect(on_error)

            # Start hardware scan
            self.hardware_mgr.scan_and_connect()

        except Exception as e:
            error_msg = f"Hardware initialization failed: {e}"
            self._log(error_msg)
            self.status_label.setText(f"✗ {error_msg}")
            self.status_label.setStyleSheet("color: red;")

    def _update_integration_time(self, value):
        """Update integration time"""
        self.integration_time = float(value)
        if self.hardware_ready and hasattr(self, 'usb'):
            try:
                self.usb.set_integration(self.integration_time)
                self._log(f"Integration time set to {self.integration_time} ms")
            except Exception as e:
                self._log(f"Error setting integration time: {e}")

    def _update_polarizer_mode(self, index):
        """Update polarizer mode"""
        mode = 's' if index == 0 else 'p'
        self.current_mode = mode
        if self.hardware_ready and hasattr(self, 'controller'):
            try:
                self.controller.set_mode(mode)
                self._log(f"Polarizer mode set to {mode.upper()}")
            except Exception as e:
                self._log(f"Error setting polarizer mode: {e}")

    def _update_led_intensity(self, channel, value):
        """Update LED intensity"""
        self.led_intensities[channel] = value
        self.led_labels[channel].setText(str(value))

        if self.hardware_ready and hasattr(self, 'controller'):
            try:
                self.controller.set_intensity(channel, value)
            except Exception as e:
                self._log(f"Error setting LED {channel}: {e}")

    def _start_acquisition(self):
        """Start live acquisition"""
        if not self.hardware_ready:
            self._log("ERROR: Hardware not ready!")
            return

        self._log("Starting live acquisition...")

        # Set integration time
        try:
            self.usb.set_integration(self.integration_time)
        except Exception as e:
            self._log(f"Error setting integration time: {e}")
            return

        # Set polarizer mode
        try:
            self.controller.set_mode(self.current_mode)
        except Exception as e:
            self._log(f"Error setting polarizer mode: {e}")
            return

        # Set LED intensities
        for ch, intensity in self.led_intensities.items():
            try:
                self.controller.set_intensity(ch, intensity)
            except Exception as e:
                self._log(f"Error setting LED {ch}: {e}")

        self.is_acquiring = True
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

        # Start acquisition timer (10 Hz update rate)
        self.acquisition_timer.start(100)
        self._log("Live acquisition started")

    def _stop_acquisition(self):
        """Stop live acquisition"""
        self.is_acquiring = False
        self.acquisition_timer.stop()
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self._log("Live acquisition stopped")

    def _acquire_spectrum(self):
        """Acquire and display spectrum"""
        if not self.is_acquiring:
            return

        try:
            # Get wavelengths
            wavelengths = self.usb.get_wavelengths()

            # Acquire spectrum for each enabled channel
            for ch, intensity in self.led_intensities.items():
                if intensity > 0:  # Only acquire if LED is on
                    # Turn on this LED
                    self.controller.led_on(ch)

                    # Acquire spectrum
                    spectrum = self.usb.get_spectrum()

                    # Turn off LED
                    self.controller.led_off(ch)

                    # Update plot
                    if spectrum is not None and len(spectrum) > 0:
                        max_counts = np.max(spectrum)
                        saturated = max_counts > 62258

                        self.channel_curves[ch].setData(wavelengths, spectrum)

                        color = "red" if saturated else "black"
                        status = "⚠ SATURATED" if saturated else ""
                        text = f"Max: {max_counts:.0f} {status}"
                        self.channel_plots[ch]['text'].setText(text)
                        self.channel_plots[ch]['text'].setColor(color)

        except Exception as e:
            self._log(f"Acquisition error: {e}")

    def _log(self, message):
        """Add message to log"""
        self.log_text.append(message)
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )

    def closeEvent(self, event):
        """Handle window close"""
        if self.is_acquiring:
            self._stop_acquisition()

        if hasattr(self, 'hardware_mgr') and self.hardware_mgr:
            try:
                self.hardware_mgr.disconnect_all()
            except:
                pass

        event.accept()


def main():
    """Run the test UI"""
    app = QApplication(sys.argv)
    window = LiveDetectorMonitor()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
