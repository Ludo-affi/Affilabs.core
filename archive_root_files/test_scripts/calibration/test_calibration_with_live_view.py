"""Test UI - Full 6-Step Calibration with LIVE Detector Output

This runs THE EXACT SAME calibration as the main application,
with live spectrum display updating during the calibration process.
"""

import sys
import time
from pathlib import Path

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# Add project paths
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from core.hardware_manager import HardwareManager

from utils.calibration_6step import run_full_6step_calibration
from utils.device_configuration import DeviceConfiguration
from utils.logger import logger


class CalibrationWorker(QObject):
    """Worker to run calibration in background thread"""

    progress_update = Signal(str, int)  # (message, percent)
    spectrum_captured = Signal(dict)  # {channel: spectrum_data}
    calibration_complete = Signal(object)  # LEDCalibrationResult
    error_occurred = Signal(str)

    def __init__(self, usb, ctrl, device_config, detector_serial):
        super().__init__()
        self.usb = usb
        self.ctrl = ctrl
        self.device_config = device_config
        self.detector_serial = detector_serial
        self._running = True

        # Monkey-patch USB to capture spectra
        self._original_read_intensity = None

    def _progress_callback(self, message: str, progress: int = 0):
        """Progress callback for calibration"""
        self.progress_update.emit(message, progress)

    def _capture_spectrum_hook(self, *args, **kwargs):
        """Hook into read_intensity to capture and emit live data"""
        if not self._running:
            return None

        # Call original method
        result = self._original_read_intensity(*args, **kwargs)

        # Emit the spectrum for live display
        if result is not None and len(result) > 0:
            try:
                wavelengths = self.usb.get_wavelengths()
                max_counts = np.max(result)

                spectrum_data = {
                    "wavelengths": wavelengths,
                    "intensities": result,
                    "max_counts": max_counts,
                    "saturated": max_counts > 62258,
                }
                self.spectrum_captured.emit({"current": spectrum_data})
            except Exception as e:
                logger.debug(f"Spectrum capture hook error: {e}")

        return result

    def run(self):
        """Execute calibration with live monitoring"""
        try:
            # Install spectrum capture hook on read_intensity
            if hasattr(self.usb, "read_intensity"):
                self._original_read_intensity = self.usb.read_intensity
                self.usb.read_intensity = self._capture_spectrum_hook
                logger.info(
                    "✅ Installed live spectrum capture hook on read_intensity()",
                )

            # Clear USB buffer (same as main app)
            logger.info("🔄 Clearing USB buffer...")
            try:
                self.usb.set_integration(10)
                time.sleep(0.1)
                for i in range(3):
                    dummy = self.usb.read_intensity(timeout_seconds=2.0)
                    if dummy is not None:
                        logger.info(f"   Dummy read {i+1}/3: Success")
                    time.sleep(0.05)
                logger.info("✅ USB buffer cleared")
            except Exception as e:
                logger.warning(f"⚠️ USB buffer clear had issues: {e}")

            # Get LED timing
            pre_led_delay_ms = self.device_config.get_pre_led_delay_ms()
            post_led_delay_ms = self.device_config.get_post_led_delay_ms()

            # Get device type
            device_type = type(self.ctrl).__name__

            # Run EXACT same calibration as main app
            logger.info("🚀 Starting 6-step calibration...")

            cal_result = run_full_6step_calibration(
                usb=self.usb,
                ctrl=self.ctrl,
                device_type=device_type,
                device_config=self.device_config,
                detector_serial=self.detector_serial,
                pre_led_delay_ms=pre_led_delay_ms,
                post_led_delay_ms=post_led_delay_ms,
                progress_callback=self._progress_callback,
            )

            # Restore original method
            if self._original_read_intensity:
                self.usb.read_intensity = self._original_read_intensity
                logger.info("✅ Restored original read_intensity() method")

            if cal_result and cal_result.success:
                self.calibration_complete.emit(cal_result)
            else:
                error_msg = (
                    cal_result.error
                    if cal_result and hasattr(cal_result, "error")
                    else "Unknown error"
                )
                self.error_occurred.emit(f"Calibration failed: {error_msg}")

        except Exception as e:
            import traceback

            error_msg = f"Error during calibration: {e}\n{traceback.format_exc()}"
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)

    def stop(self):
        """Stop calibration"""
        self._running = False


class LiveCalibrationTestUI(QMainWindow):
    """Test UI for calibration with live detector output"""

    def __init__(self):
        super().__init__()

        self.hardware_mgr = None
        self.hardware_ready = False
        self.device_config = None
        self.calibration_thread = None
        self.calibration_worker = None

        self._setup_ui()
        self._connect_hardware()

    def _setup_ui(self):
        """Setup the user interface"""
        self.setWindowTitle("Full 6-Step Calibration - Live View")
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

        # Calibration controls
        cal_group = QGroupBox("Calibration Control")
        cal_layout = QVBoxLayout(cal_group)

        self.start_button = QPushButton("Start Full 6-Step Calibration")
        self.start_button.setEnabled(False)
        self.start_button.clicked.connect(self._start_calibration)
        self.start_button.setStyleSheet(
            "QPushButton { font-size: 14px; padding: 10px; }",
        )
        cal_layout.addWidget(self.start_button)

        self.stop_button = QPushButton("Stop Calibration")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._stop_calibration)
        cal_layout.addWidget(self.stop_button)

        controls_layout.addWidget(cal_group)
        controls_layout.addStretch()

        # Live spectrum display
        spectrum_group = QGroupBox("Live Detector Output")
        spectrum_layout = QVBoxLayout(spectrum_group)

        self.plot_widget = pg.PlotWidget(title="Live Spectrum During Calibration")
        self.plot_widget.setLabel("left", "Intensity", units="counts")
        self.plot_widget.setLabel("bottom", "Wavelength", units="nm")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setBackground("w")
        self.plot_widget.setYRange(0, 70000)

        # Add spectrum curve
        self.spectrum_curve = self.plot_widget.plot(pen=pg.mkPen(color="b", width=2))

        # Add saturation line
        saturation_line = pg.InfiniteLine(
            pos=62258,
            angle=0,
            pen=pg.mkPen(color="r", width=2, style=Qt.DashLine),
            label="Saturation (95%)",
            labelOpts={"position": 0.95},
        )
        self.plot_widget.addItem(saturation_line)

        # Add max counts label
        self.max_counts_text = pg.TextItem(
            text="Max: 0",
            anchor=(1, 0),
            color=(0, 0, 0),
        )
        self.max_counts_text.setPos(800, 60000)
        self.plot_widget.addItem(self.max_counts_text)

        spectrum_layout.addWidget(self.plot_widget)
        main_layout.addWidget(spectrum_group, stretch=2)

        # Progress and log
        log_group = QGroupBox("Calibration Progress")
        log_layout = QVBoxLayout(log_group)

        self.progress_label = QLabel("Ready")
        self.progress_label.setFont(QFont("Arial", 11, QFont.Bold))
        log_layout.addWidget(self.progress_label)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        log_layout.addWidget(self.log_text)

        main_layout.addWidget(log_group, stretch=1)

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
                s_pos = servo_positions["s"]
                p_pos = servo_positions["p"]
                self._log(f"Servo positions: S={s_pos}°, P={p_pos}°")

                # Get detector serial
                self.detector_serial = getattr(self.usb, "serial_number", "Unknown")

                # Update status
                ctrl_name = info.get("ctrl_type", "Unknown")
                spec_name = info.get("spectrometer", "Unknown")
                self.status_label.setText(
                    f"✓ Controller: {ctrl_name}\n"
                    f"✓ Detector: {spec_name}\n"
                    f"✓ Servo: S={s_pos}° P={p_pos}°",
                )
                self.status_label.setStyleSheet("color: green;")

                self.hardware_ready = True
                self.start_button.setEnabled(True)
                self._log(
                    "✅ Hardware ready! Click Start to begin calibration with live view",
                )

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

    def _start_calibration(self):
        """Start calibration with live monitoring"""
        if not self.hardware_ready:
            self._log("ERROR: Hardware not ready!")
            return

        if not self.controller or not self.usb:
            self._log("ERROR: Controller or spectrometer not connected!")
            return

        self._log("\n" + "=" * 80)
        self._log("STARTING FULL 6-STEP CALIBRATION")
        self._log("=" * 80)

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

        # Create worker thread
        self.calibration_worker = CalibrationWorker(
            self.usb,
            self.controller,
            self.device_config,
            self.detector_serial,
        )
        self.calibration_thread = QThread()
        self.calibration_worker.moveToThread(self.calibration_thread)

        # Connect signals
        self.calibration_thread.started.connect(self.calibration_worker.run)
        self.calibration_worker.progress_update.connect(self._update_progress)
        self.calibration_worker.spectrum_captured.connect(self._update_spectrum)
        self.calibration_worker.calibration_complete.connect(self._calibration_complete)
        self.calibration_worker.error_occurred.connect(self._calibration_error)
        self.calibration_worker.calibration_complete.connect(
            self.calibration_thread.quit,
        )
        self.calibration_worker.error_occurred.connect(self.calibration_thread.quit)
        self.calibration_thread.finished.connect(self._cleanup_thread)

        # Start thread
        self.calibration_thread.start()

    def _stop_calibration(self):
        """Stop calibration"""
        if self.calibration_worker:
            self._log("Stopping calibration...")
            self.calibration_worker.stop()
            self.stop_button.setEnabled(False)

    def _update_progress(self, message: str, progress: int):
        """Update progress display"""
        self.progress_label.setText(f"[{progress}%] {message}")
        self._log(f"Progress: {message}")

    def _update_spectrum(self, spectrum_data):
        """Update live spectrum display"""
        data = spectrum_data.get("current")
        if data:
            wavelengths = data["wavelengths"]
            intensities = data["intensities"]
            max_counts = data["max_counts"]
            saturated = data["saturated"]

            # Update plot
            self.spectrum_curve.setData(wavelengths, intensities)

            # Update max counts label
            color = "red" if saturated else "black"
            status = "⚠ SATURATED" if saturated else ""
            text = f"Max: {max_counts:.0f} {status}"
            self.max_counts_text.setText(text)
            self.max_counts_text.setColor(color)

    def _calibration_complete(self, result):
        """Handle calibration completion"""
        self._log("\n" + "=" * 80)
        self._log("CALIBRATION COMPLETE!")
        self._log("=" * 80)
        self._log(f"Success: {result.success}")
        self._log(f"S-mode Integration: {result.s_integration_time:.2f} ms")
        self._log(f"P-mode Integration: {result.p_integration_time:.2f} ms")
        self._log(
            f"Wavelength Range: {result.wavelength_min:.1f} - {result.wavelength_max:.1f} nm",
        )
        self._log(f"S-mode LEDs: {result.s_mode_intensity}")
        self._log(f"P-mode LEDs: {result.p_mode_intensity}")

        # QC results
        self._log("\nQC Results:")
        for ch, qc in result.qc_results.items():
            self._log(f"  Channel {ch.upper()}:")
            self._log(f"    SPR λ: {qc['spr_wavelength']:.1f} nm")
            self._log(f"    FWHM: {qc['fwhm']:.1f} nm ({qc['fwhm_quality']})")
            self._log(f"    P/S Ratio: {qc['p_s_ratio']:.2f}")
            self._log(
                f"    Orientation: {'✓ CORRECT' if qc['orientation_correct'] else '✗ INVERTED'}",
            )
            self._log(f"    Overall: {'✓ PASS' if qc['overall_pass'] else '✗ FAIL'}")
            if qc["warnings"]:
                for warning in qc["warnings"]:
                    self._log(f"      ⚠ {warning}")

        self.progress_label.setText("✅ Calibration Complete!")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def _calibration_error(self, error_msg):
        """Handle calibration error"""
        self._log("\n" + "=" * 80)
        self._log(f"CALIBRATION ERROR: {error_msg}")
        self._log("=" * 80)
        self.progress_label.setText("❌ Calibration Failed")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def _cleanup_thread(self):
        """Clean up calibration thread"""
        if self.calibration_thread:
            self.calibration_thread.deleteLater()
            self.calibration_thread = None
        if self.calibration_worker:
            self.calibration_worker.deleteLater()
            self.calibration_worker = None

    def _log(self, message):
        """Add message to log"""
        self.log_text.append(message)
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum(),
        )

    def closeEvent(self, event):
        """Handle window close"""
        if self.calibration_thread and self.calibration_thread.isRunning():
            self._stop_calibration()
            self.calibration_thread.wait(3000)

        if hasattr(self, "hardware_mgr") and self.hardware_mgr:
            try:
                self.hardware_mgr.disconnect_all()
            except:
                pass

        event.accept()


def main():
    """Run the test UI"""
    app = QApplication(sys.argv)
    window = LiveCalibrationTestUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
