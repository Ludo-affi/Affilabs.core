"""Enhanced Test UI - Full 6-Step Calibration with LIVE Controls

Features:
- Live detector spectrum output during calibration
- Current polarizer position display (always visible)
- Polarizer calibration button
- Custom position control field
"""

import sys
import time
from pathlib import Path

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSpinBox,
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
        """Stop the calibration worker"""
        self._running = False


class LiveCalibrationUI(QMainWindow):
    """Enhanced test UI with live controls and position management"""

    def __init__(self):
        super().__init__()

        self.hardware_mgr = None
        self.hardware_ready = False
        self.device_config = None
        self.calibration_thread = None
        self.calibration_worker = None
        self.current_mode = None  # Track current polarizer mode

        # Position monitoring timer
        self.position_timer = QTimer()
        self.position_timer.timeout.connect(self._update_position_display)
        self.position_timer.setInterval(500)  # Update every 500ms

        self._setup_ui()
        self._connect_hardware()

    def _setup_ui(self):
        """Setup the user interface"""
        self.setWindowTitle("Live Calibration & Position Control UI")
        self.resize(1800, 1000)

        # Main widget
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        # ===== LEFT PANEL: Controls =====
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setMaximumWidth(450)

        # --- Hardware Status ---
        status_group = QGroupBox("Hardware Status")
        status_layout = QVBoxLayout(status_group)
        self.status_label = QLabel("Initializing...")
        self.status_label.setFont(QFont("Consolas", 9))
        self.status_label.setWordWrap(True)
        status_layout.addWidget(self.status_label)
        left_layout.addWidget(status_group)

        # --- Current Polarizer Position (ALWAYS VISIBLE) ---
        position_group = QGroupBox("⚙️ Current Polarizer Position")
        position_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        position_layout = QVBoxLayout(position_group)

        self.position_display = QLabel("Mode: Unknown\nAngle: ---°")
        self.position_display.setFont(QFont("Arial", 14, QFont.Bold))
        self.position_display.setStyleSheet("""
            QLabel {
                background-color: #e8f4f8;
                border: 2px solid #2196F3;
                border-radius: 8px;
                padding: 15px;
                color: #1976D2;
            }
        """)
        self.position_display.setAlignment(Qt.AlignCenter)
        position_layout.addWidget(self.position_display)

        left_layout.addWidget(position_group)

        # --- Calibration Control ---
        cal_group = QGroupBox("Calibration Control")
        cal_layout = QVBoxLayout(cal_group)

        self.calibrate_button = QPushButton("🔧 Run Polarizer Calibration")
        self.calibrate_button.setEnabled(False)
        self.calibrate_button.clicked.connect(self._start_calibration)
        self.calibrate_button.setStyleSheet("""
            QPushButton {
                font-size: 13px;
                padding: 12px;
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        cal_layout.addWidget(self.calibrate_button)

        self.stop_button = QPushButton("⏹ Stop Calibration")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._stop_calibration)
        self.stop_button.setStyleSheet("""
            QPushButton {
                padding: 8px;
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        cal_layout.addWidget(self.stop_button)

        left_layout.addWidget(cal_group)

        # --- Custom Position Control ---
        custom_group = QGroupBox("Manual Position Control")
        custom_layout = QVBoxLayout(custom_group)

        # Position mode selector
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Mode:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["S (Parallel)", "P (Perpendicular)"])
        self.mode_combo.setEnabled(False)
        mode_layout.addWidget(self.mode_combo)
        custom_layout.addLayout(mode_layout)

        # Custom angle input
        angle_layout = QHBoxLayout()
        angle_layout.addWidget(QLabel("Custom Angle:"))
        self.custom_angle_input = QSpinBox()
        self.custom_angle_input.setRange(0, 180)
        self.custom_angle_input.setValue(90)
        self.custom_angle_input.setSuffix("°")
        self.custom_angle_input.setEnabled(False)
        angle_layout.addWidget(self.custom_angle_input)
        custom_layout.addLayout(angle_layout)

        # Control buttons
        button_layout = QHBoxLayout()

        self.set_mode_button = QPushButton("Set Mode")
        self.set_mode_button.setEnabled(False)
        self.set_mode_button.clicked.connect(self._set_polarizer_mode)
        button_layout.addWidget(self.set_mode_button)

        self.set_custom_button = QPushButton("Set Custom Angle")
        self.set_custom_button.setEnabled(False)
        self.set_custom_button.clicked.connect(self._set_custom_position)
        button_layout.addWidget(self.set_custom_button)

        custom_layout.addLayout(button_layout)

        # Instructions
        instructions = QLabel(
            "<small><b>Instructions:</b><br>"
            "• Use 'Set Mode' for configured S/P positions<br>"
            "• Use 'Set Custom Angle' to test any position<br>"
            "• Position updates automatically above</small>",
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("color: #555; margin-top: 10px;")
        custom_layout.addWidget(instructions)

        left_layout.addWidget(custom_group)

        # --- Progress Log ---
        log_group = QGroupBox("Activity Log")
        log_layout = QVBoxLayout(log_group)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 8))
        self.log_text.setMaximumHeight(200)
        log_layout.addWidget(self.log_text)

        left_layout.addWidget(log_group)
        left_layout.addStretch()

        main_layout.addWidget(left_panel)

        # ===== RIGHT PANEL: Live Spectrum Display =====
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # Live spectrum display
        spectrum_group = QGroupBox("📊 Live Detector Output")
        spectrum_group.setStyleSheet(
            "QGroupBox { font-size: 13px; font-weight: bold; }",
        )
        spectrum_layout = QVBoxLayout(spectrum_group)

        # Progress label
        self.progress_label = QLabel("Ready to calibrate")
        self.progress_label.setFont(QFont("Arial", 11, QFont.Bold))
        self.progress_label.setStyleSheet(
            "padding: 8px; background-color: #f0f0f0; border-radius: 4px;",
        )
        spectrum_layout.addWidget(self.progress_label)

        # Plot widget
        self.plot_widget = pg.PlotWidget(title="Live Spectrum During Calibration")
        self.plot_widget.setLabel("left", "Intensity", units="counts")
        self.plot_widget.setLabel("bottom", "Wavelength", units="nm")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setBackground("w")
        self.plot_widget.setYRange(0, 70000)

        # Add spectrum curve
        self.spectrum_curve = self.plot_widget.plot(
            pen=pg.mkPen(color="#2196F3", width=2.5),
        )

        # Add saturation line
        saturation_line = pg.InfiniteLine(
            pos=62258,
            angle=0,
            pen=pg.mkPen(color="r", width=2, style=Qt.DashLine),
            label="Saturation (95%)",
            labelOpts={"position": 0.95, "color": "r"},
        )
        self.plot_widget.addItem(saturation_line)

        # Add max counts label
        self.max_counts_text = pg.TextItem(
            text="Max: 0 counts",
            anchor=(1, 0),
            color=(0, 0, 0),
        )
        self.max_counts_text.setPos(800, 60000)
        self.plot_widget.addItem(self.max_counts_text)

        spectrum_layout.addWidget(self.plot_widget)
        right_layout.addWidget(spectrum_group)

        main_layout.addWidget(right_panel, stretch=1)

    def _connect_hardware(self):
        """Initialize hardware connections"""
        try:
            self._log("🔄 Initializing hardware...")

            # Load device config
            config_path = Path(__file__).parent / "device_config.json"
            self.device_config = DeviceConfiguration(str(config_path))
            self._log(f"✓ Device config loaded: {config_path}")

            # Initialize hardware manager
            self._log("🔍 Scanning for hardware...")
            self.hardware_mgr = HardwareManager()

            def on_progress(msg):
                self._log(msg)

            def on_connected(info):
                self._log(f"✓ Hardware connected: {info}")

                # Store references
                self.controller = self.hardware_mgr.ctrl
                self.usb = self.hardware_mgr.usb

                if not self.controller or not self.usb:
                    self._log("❌ ERROR: Controller or spectrometer missing!")
                    return

                # Get servo positions from config
                servo_positions = self.device_config.get_servo_positions()
                s_pos = servo_positions["s"]
                p_pos = servo_positions["p"]
                self._log(f"✓ Servo positions: S={s_pos}°, P={p_pos}°")

                # Get detector serial
                self.detector_serial = getattr(self.usb, "serial_number", "Unknown")

                # Update status
                ctrl_name = info.get("ctrl_type", "Unknown")
                spec_name = info.get("spectrometer", "Unknown")
                self.status_label.setText(
                    f"✓ Controller: {ctrl_name}\n"
                    f"✓ Detector: {spec_name} (SN: {self.detector_serial})\n"
                    f"✓ Configured Positions:\n"
                    f"   S-mode: {s_pos}°\n"
                    f"   P-mode: {p_pos}°",
                )
                self.status_label.setStyleSheet("color: green;")

                self.hardware_ready = True
                self.calibrate_button.setEnabled(True)
                self.set_mode_button.setEnabled(True)
                self.set_custom_button.setEnabled(True)
                self.mode_combo.setEnabled(True)
                self.custom_angle_input.setEnabled(True)

                self._log("✅ Hardware ready!")

                # Start position monitoring
                self.position_timer.start()
                self._update_position_display()

            def on_error(error_msg):
                self._log(f"❌ Hardware error: {error_msg}")
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

    def _update_position_display(self):
        """Update the current polarizer position display"""
        if not self.hardware_ready or not self.controller:
            return

        try:
            # Get current position from controller
            # Note: Most controllers don't report actual position, so we track mode
            servo_positions = self.device_config.get_servo_positions()

            if self.current_mode == "s":
                angle = servo_positions["s"]
                mode_text = "S-MODE (Parallel)"
                color = "#1976D2"  # Blue
            elif self.current_mode == "p":
                angle = servo_positions["p"]
                mode_text = "P-MODE (Perpendicular)"
                color = "#E91E63"  # Pink
            else:
                mode_text = "Unknown"
                angle = "---"
                color = "#757575"  # Gray

            self.position_display.setText(f"{mode_text}\nAngle: {angle}°")
            self.position_display.setStyleSheet(f"""
                QLabel {{
                    background-color: {color}22;
                    border: 3px solid {color};
                    border-radius: 8px;
                    padding: 15px;
                    color: {color};
                }}
            """)

        except Exception as e:
            logger.debug(f"Position update error: {e}")

    def _set_polarizer_mode(self):
        """Set polarizer to configured S or P mode"""
        if not self.hardware_ready:
            self._log("❌ Hardware not ready!")
            return

        try:
            mode_text = self.mode_combo.currentText()
            mode = "s" if "Parallel" in mode_text else "p"

            self._log(f"🔄 Setting polarizer to {mode.upper()}-mode...")

            success = self.controller.set_mode(mode)

            if success:
                self.current_mode = mode
                self._update_position_display()

                servo_positions = self.device_config.get_servo_positions()
                angle = servo_positions[mode]
                self._log(f"✅ Polarizer set to {mode.upper()}-mode ({angle}°)")
            else:
                self._log(f"❌ Failed to set {mode.upper()}-mode")

        except Exception as e:
            self._log(f"❌ Error setting mode: {e}")

    def _set_custom_position(self):
        """Set polarizer to custom angle"""
        if not self.hardware_ready:
            self._log("❌ Hardware not ready!")
            return

        try:
            angle = self.custom_angle_input.value()

            self._log(f"🔄 Setting polarizer to custom position: {angle}°...")

            # Use controller's direct position command if available
            if hasattr(self.controller, "set_servo_position"):
                success = self.controller.set_servo_position(angle)
            elif hasattr(self.controller, "_send_command"):
                # Generic command sending
                cmd = f"SERVO {angle}"
                self.controller._send_command(cmd)
                success = True
            else:
                self._log("⚠️ Custom position not supported by this controller")
                return

            if success:
                self.current_mode = None  # Custom position
                self._log(f"✅ Polarizer moved to {angle}°")
                self._log(
                    "⚠️ Note: You're at a custom position. Run calibration to return to configured settings.",
                )
            else:
                self._log("❌ Failed to set custom position")

        except Exception as e:
            self._log(f"❌ Error setting custom position: {e}")

    def _start_calibration(self):
        """Start full 6-step calibration with live monitoring"""
        if not self.hardware_ready:
            self._log("❌ Hardware not ready!")
            return

        if not self.controller or not self.usb:
            self._log("❌ Controller or spectrometer not connected!")
            return

        self._log("\n" + "=" * 80)
        self._log("🚀 STARTING FULL 6-STEP POLARIZER CALIBRATION")
        self._log("=" * 80)

        self.calibrate_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.set_mode_button.setEnabled(False)
        self.set_custom_button.setEnabled(False)

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
        self.calibration_worker.progress_update.connect(self._on_progress_update)
        self.calibration_worker.spectrum_captured.connect(self._update_spectrum)
        self.calibration_worker.calibration_complete.connect(self._calibration_complete)
        self.calibration_worker.error_occurred.connect(self._calibration_error)
        self.calibration_thread.finished.connect(self._cleanup_calibration)

        # Start calibration
        self.calibration_thread.start()

    def _stop_calibration(self):
        """Stop running calibration"""
        if self.calibration_worker:
            self._log("⏹ Stopping calibration...")
            self.calibration_worker.stop()

        if self.calibration_thread:
            self.calibration_thread.quit()
            self.calibration_thread.wait()

    def _on_progress_update(self, message: str, progress: int):
        """Handle calibration progress updates"""
        self.progress_label.setText(f"[{progress}%] {message}")
        self._log(f"[{progress}%] {message}")

    def _update_spectrum(self, spectrum_dict):
        """Update live spectrum plot"""
        try:
            if "current" not in spectrum_dict:
                return

            data = spectrum_dict["current"]
            wavelengths = data["wavelengths"]
            intensities = data["intensities"]
            max_counts = data["max_counts"]
            saturated = data["saturated"]

            # Update plot
            self.spectrum_curve.setData(wavelengths, intensities)

            # Update max counts label
            saturation_status = " ⚠️ SATURATED!" if saturated else ""
            self.max_counts_text.setText(
                f"Max: {max_counts:.0f} counts{saturation_status}",
            )

            if saturated:
                self.max_counts_text.setColor((255, 0, 0))
            else:
                self.max_counts_text.setColor((0, 128, 0))

        except Exception as e:
            logger.debug(f"Spectrum update error: {e}")

    def _calibration_complete(self, result):
        """Handle calibration completion"""
        self._log("\n" + "=" * 80)
        self._log("✅ CALIBRATION COMPLETE")
        self._log("=" * 80)

        # Log QC results
        if hasattr(result, "qc_data") and result.qc_data:
            self._log("\n📊 Quality Control Results:")
            qc = result.qc_data

            for ch in ["A", "B", "C", "D"]:
                if ch in qc:
                    data = qc[ch]
                    ps_ratio = data.get("p_s_ratio", 0)
                    orientation = "✓" if data.get("orientation_correct", False) else "✗"
                    self._log(
                        f"  Channel {ch}: P/S ratio = {ps_ratio:.3f} {orientation}",
                    )

            overall_pass = qc.get("overall_pass", False)
            status = "✅ PASS" if overall_pass else "❌ FAIL"
            self._log(f"\nOverall Status: {status}")

        self.progress_label.setText("✅ Calibration Complete!")
        self.progress_label.setStyleSheet(
            "padding: 8px; background-color: #4CAF50; color: white; "
            "border-radius: 4px; font-weight: bold;",
        )

        self.calibrate_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.set_mode_button.setEnabled(True)
        self.set_custom_button.setEnabled(True)

    def _calibration_error(self, error_msg):
        """Handle calibration error"""
        self._log(f"\n❌ CALIBRATION ERROR:\n{error_msg}")
        self.progress_label.setText("❌ Calibration Failed")
        self.progress_label.setStyleSheet(
            "padding: 8px; background-color: #f44336; color: white; "
            "border-radius: 4px; font-weight: bold;",
        )

        self.calibrate_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.set_mode_button.setEnabled(True)
        self.set_custom_button.setEnabled(True)

    def _cleanup_calibration(self):
        """Clean up calibration thread"""
        if self.calibration_thread:
            self.calibration_thread.deleteLater()
            self.calibration_thread = None
        if self.calibration_worker:
            self.calibration_worker.deleteLater()
            self.calibration_worker = None

    def _log(self, message: str):
        """Add message to log"""
        self.log_text.append(message)
        # Auto-scroll to bottom
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def closeEvent(self, event):
        """Handle window close"""
        self.position_timer.stop()

        if self.calibration_thread and self.calibration_thread.isRunning():
            self._stop_calibration()

        if self.hardware_mgr:
            try:
                self.hardware_mgr.cleanup()
            except Exception as e:
                logger.debug(f"Error during hardware cleanup: {e}")

        event.accept()


def main():
    app = QApplication(sys.argv)

    # Set application style
    app.setStyle("Fusion")

    window = LiveCalibrationUI()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
