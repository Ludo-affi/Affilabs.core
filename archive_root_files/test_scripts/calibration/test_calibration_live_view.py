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
    QTabWidget, QSlider, QComboBox, QCheckBox
)
from PySide6.QtCore import Qt, QTimer, Signal, QObject, QThread
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
        self.auto_start = True  # default auto-start behavior

        # Live acquisition
        self.acquisition_timer = QTimer()
        self.acquisition_timer.timeout.connect(self._acquire_spectrum)
        self.is_acquiring = False
        # Cached wavelengths and frame counter for reduced overhead/logging
        self._wavelengths = None
        self._frame_count = 0

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

        # Auto-start checkbox
        self.auto_start_checkbox = QCheckBox("Auto-start when hardware ready")
        self.auto_start_checkbox.setChecked(True)
        self.auto_start_checkbox.stateChanged.connect(lambda s: setattr(self, 'auto_start', bool(s)))
        acq_layout.addWidget(self.auto_start_checkbox)

        controls_layout.addWidget(acq_group)

        # Servo calibration group (manual fine tuning)
        servo_group = QGroupBox("Polarizer Servo Calibration")
        servo_layout = QVBoxLayout(servo_group)
        servo_pos_layout = QHBoxLayout()
        servo_pos_layout.addWidget(QLabel("S (°):"))
        self.servo_s_spin = QSpinBox()
        self.servo_s_spin.setRange(0, 180)
        self.servo_s_spin.setValue(10)
        servo_pos_layout.addWidget(self.servo_s_spin)
        servo_pos_layout.addWidget(QLabel("P (°):"))
        self.servo_p_spin = QSpinBox()
        self.servo_p_spin.setRange(0, 180)
        self.servo_p_spin.setValue(100)
        servo_pos_layout.addWidget(self.servo_p_spin)
        servo_layout.addLayout(servo_pos_layout)

        apply_servo_layout = QHBoxLayout()
        self.apply_servo_button = QPushButton("Move Servo")
        self.apply_servo_button.setEnabled(False)
        self.apply_servo_button.clicked.connect(self._apply_servo_positions)
        apply_servo_layout.addWidget(self.apply_servo_button)
        self.save_servo_checkbox = QCheckBox("Save to config (no EEPROM)")
        apply_servo_layout.addWidget(self.save_servo_checkbox)
        servo_layout.addLayout(apply_servo_layout)

        self.current_servo_label = QLabel("Current: S=--° P=--°")
        self.current_servo_label.setFont(QFont("Consolas", 10))
        servo_layout.addWidget(self.current_servo_label)
        servo_note = QLabel("Calibration-only movement. Use S/P Mode combo for normal operation.")
        servo_note.setWordWrap(True)
        servo_note.setStyleSheet("color:#555;")
        servo_layout.addWidget(servo_note)

        controls_layout.addWidget(servo_group)

        # Polarization calibration scan group
        calib_group = QGroupBox("Polarization Calibration Scan")
        calib_layout = QVBoxLayout(calib_group)
        self.run_calib_button = QPushButton("Run Polarization Scan")
        self.run_calib_button.setEnabled(False)
        self.run_calib_button.clicked.connect(self._run_polarization_scan)
        calib_layout.addWidget(self.run_calib_button)
        self.calib_status_label = QLabel("Idle")
        self.calib_status_label.setFont(QFont("Consolas", 10))
        calib_layout.addWidget(self.calib_status_label)
        controls_layout.addWidget(calib_group)

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

        # Prepare live spectrum tab widget (added later inside splitter)
        self.plot_tabs = QTabWidget()

        # Create plot widgets for each channel (live spectrum)
        self.channel_plots = {}
        self.channel_curves = {}
        for ch in ['a', 'b', 'c', 'd']:
            plot_widget = pg.PlotWidget(title=f"Channel {ch.upper()} - Live Spectrum")
            plot_widget.setLabel('left', 'Intensity', units='counts')
            plot_widget.setLabel('bottom', 'Wavelength', units='nm')
            plot_widget.showGrid(x=True, y=True, alpha=0.3)
            plot_widget.setBackground('w')
            plot_widget.setYRange(0, 70000)

            curve = plot_widget.plot(pen=pg.mkPen(color='b', width=2))
            self.channel_curves[ch] = curve

            saturation_line = pg.InfiniteLine(
                pos=62258,
                angle=0,
                pen=pg.mkPen(color='r', width=2, style=Qt.DashLine),
                label='Saturation (95%)',
                labelOpts={'position': 0.95}
            )
            plot_widget.addItem(saturation_line)

            text_item = pg.TextItem(
                text="Max: 0",
                anchor=(1, 0),
                color=(0, 0, 0)
            )
            text_item.setPos(800, 60000)
            plot_widget.addItem(text_item)

            self.channel_plots[ch] = {'widget': plot_widget, 'text': text_item}
            self.plot_tabs.addTab(plot_widget, f"Channel {ch.upper()}")

        # Calibration (polarization) plot
        self.polar_scan_plot = pg.PlotWidget(title="Polarization Calibration Plot (Intensity vs Angle)")
        self.polar_scan_plot.setLabel('left', 'Intensity', units='counts')
        self.polar_scan_plot.setLabel('bottom', 'Angle', units='deg')
        self.polar_scan_plot.showGrid(x=True, y=True, alpha=0.3)
        self.polar_scan_plot.setBackground('w')
        self.polar_scan_plot.setYRange(0, 70000)
        self.scan_curve_s = self.polar_scan_plot.plot(pen=pg.mkPen(color='g', width=2), name='S-mode')
        self.scan_curve_p = self.polar_scan_plot.plot(pen=pg.mkPen(color='m', width=2), name='P-mode')

        # Splitter for 30/70 layout (top small calibration plot, bottom large live spectra)
        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self.polar_scan_plot)
        splitter.addWidget(self.plot_tabs)
        splitter.setSizes([300, 700])  # Approximate 30/70 ratio
        main_layout.addWidget(splitter, stretch=1)

        # Log output below splitter
        log_group = QGroupBox("Status Log")
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setMaximumHeight(150)
        log_layout.addWidget(self.log_text)
        main_layout.addWidget(log_group)

        # Data containers for scan
        self._scan_angles = []
        self._scan_s_intensity = []
        self._scan_p_intensity = []
        self._calibration_worker = None

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

                # Populate servo calibration widgets
                try:
                    self.servo_s_spin.setValue(int(s_pos))
                    self.servo_p_spin.setValue(int(p_pos))
                    self.current_servo_label.setText(f"Current: S={s_pos}° P={p_pos}°")
                    self.apply_servo_button.setEnabled(True)
                    self.run_calib_button.setEnabled(True)
                except Exception as e:
                    self._log(f"Servo UI init failed: {e}")

                # Auto-start acquisition if enabled
                if getattr(self, 'auto_start', False) and self.auto_start_checkbox.isChecked():
                    self._log("Auto-start enabled -> starting acquisition")
                    # Defer start slightly to allow UI to finish paint cycle
                    QTimer.singleShot(150, self._start_acquisition)

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

        # Cache wavelengths once (fallback to indices if unavailable later)
        try:
            if hasattr(self.usb, 'wavelengths'):
                self._wavelengths = self.usb.wavelengths
            elif hasattr(self.usb, 'read_wavelength'):
                self._wavelengths = self.usb.read_wavelength()
        except Exception:
            self._wavelengths = None

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
            self._frame_count += 1
            wavelengths = self._wavelengths  # Cached value (may be None)

            any_led_on = any(v > 0 for v in self.led_intensities.values())

            # Dark spectrum path (no LEDs active)
            if not any_led_on:
                dark = None
                if hasattr(self.usb, 'read_intensity'):
                    dark = self.usb.read_intensity()
                if dark is not None and len(dark) > 0:
                    if wavelengths is None:
                        wavelengths = np.arange(len(dark))
                    max_counts = float(np.max(dark))
                    saturated = max_counts > 62258
                    color = "red" if saturated else "black"
                    status = "⚠ SATURATED" if saturated else ""
                    text = f"Dark Max: {max_counts:.0f} {status}"
                    for ch in self.channel_curves.keys():
                        self.channel_curves[ch].setData(wavelengths, dark)
                        self.channel_plots[ch]['text'].setText(text)
                        self.channel_plots[ch]['text'].setColor(color)
                    if self._frame_count % 30 == 0:
                        self._log(f"Dark spectrum updated (len={len(dark)})")
                else:
                    if self._frame_count % 30 == 0:
                        self._log("Dark acquisition returned no data")
                return

            # Active LED acquisition: read each channel that has intensity >0
            for ch, intensity in self.led_intensities.items():
                if intensity <= 0:
                    continue

                # Ensure channel is turned on (only if controller supports it)
                if hasattr(self.controller, 'turn_on_channel'):
                    try:
                        self.controller.turn_on_channel(ch)
                    except Exception:
                        pass

                spectrum = None
                if hasattr(self.usb, 'read_intensity'):
                    spectrum = self.usb.read_intensity()

                if spectrum is not None and len(spectrum) > 0:
                    if wavelengths is None:
                        wavelengths = np.arange(len(spectrum))
                    max_counts = float(np.max(spectrum))
                    saturated = max_counts > 62258
                    self.channel_curves[ch].setData(wavelengths, spectrum)
                    color = "red" if saturated else "black"
                    status = "⚠ SATURATED" if saturated else ""
                    text = f"Max: {max_counts:.0f} {status}"
                    self.channel_plots[ch]['text'].setText(text)
                    self.channel_plots[ch]['text'].setColor(color)
                    if self._frame_count % 50 == 0:
                        self._log(f"Ch {ch.upper()} spectrum len={len(spectrum)} max={max_counts:.0f}")
                else:
                    if self._frame_count % 50 == 0:
                        self._log(f"Ch {ch.upper()} spectrum read returned no data")

        except Exception as e:
            self._log(f"Acquisition error: {e}")

    def _apply_servo_positions(self):
        """Move servo to specified S/P positions (calibration only)."""
        if not self.hardware_ready or not hasattr(self, 'controller') or self.controller is None:
            self._log("Servo move skipped: hardware not ready")
            return
        s_pos = self.servo_s_spin.value()
        p_pos = self.servo_p_spin.value()
        moved = False
        if hasattr(self.controller, 'servo_move_calibration_only'):
            try:
                moved = self.controller.servo_move_calibration_only(s=s_pos, p=p_pos)
            except Exception as e:
                self._log(f"Servo move error: {e}")
                moved = False
        else:
            self._log("Controller lacks calibration-only servo move method")
        if moved:
            self.current_servo_label.setText(f"Current: S={s_pos}° P={p_pos}°")
            self._log(f"Servo moved (calibration-only): S={s_pos}° P={p_pos}°")
            if self.save_servo_checkbox.isChecked() and hasattr(self, 'device_config') and self.device_config:
                try:
                    self.device_config.set_servo_positions(s_pos, p_pos)
                    self.device_config.save(auto_sync_eeprom=False)
                    self._log("Positions saved to device_config.json (no EEPROM flash)")
                except Exception as e:
                    self._log(f"Save to config failed: {e}")
        else:
            self._log("Servo move failed")

    # ================= Polarization Scan Worker =====================
    class _PolarizationScanWorker(QThread):
        progress = Signal(dict)  # {stage, angle, s_intensity, p_intensity}
        finished = Signal(dict)  # {s_pos, p_pos, ratio, success, details}

        def __init__(self, controller, usb, integration_time=20.0, led_channel='a', led_intensity=120):
            super().__init__()
            self.controller = controller
            self.usb = usb
            self.integration_time = integration_time
            self.led_channel = led_channel
            self.led_intensity = led_intensity
            self._abort = False

        def abort(self):
            self._abort = True

        def _read_mode_intensity(self, mode: str) -> float:
            import time, numpy as np
            try:
                if hasattr(self.controller, 'set_mode'):
                    self.controller.set_mode(mode)
                time.sleep(0.05)
                if hasattr(self.usb, 'read_intensity'):
                    spec = self.usb.read_intensity()
                    if spec is not None and len(spec) > 0:
                        return float(np.max(spec))
            except Exception:
                return 0.0
            return 0.0

        def run(self):
            import time, numpy as np
            try:
                # Set temporary integration time
                try:
                    if hasattr(self.usb, 'set_integration'):
                        self.usb.set_integration(self.integration_time)
                        time.sleep(0.05)
                except Exception:
                    pass

                # Ensure LED has sufficient intensity
                try:
                    if hasattr(self.controller, 'set_intensity'):
                        self.controller.set_intensity(self.led_channel, self.led_intensity)
                        time.sleep(0.05)
                except Exception:
                    pass

                # ---------------- Stage 1: Coarse sweep ----------------
                coarse_angles = list(range(0, 181, 30))  # 0,30,...,180
                coarse_s = []
                coarse_p = []
                for ang in coarse_angles:
                    if self._abort:
                        break
                    if hasattr(self.controller, 'servo_move_calibration_only'):
                        self.controller.servo_move_calibration_only(s=ang, p=(ang + 90) % 180)
                        time.sleep(0.05)
                    s_int = self._read_mode_intensity('s')
                    p_int = self._read_mode_intensity('p')
                    coarse_s.append(s_int)
                    coarse_p.append(p_int)
                    self.progress.emit({'stage': 'coarse', 'angle': ang, 's_intensity': s_int, 'p_intensity': p_int})

                if len(coarse_s) == 0:
                    self.finished.emit({'s_pos': None, 'p_pos': None, 'ratio': None, 'success': False, 'details': 'No coarse data'})
                    return
                max_idx = int(np.argmax(coarse_s))
                s_center = coarse_angles[max_idx]

                # ---------------- Stage 2: Refinement ----------------
                # ±15 region, step 5
                refine_angles = []
                for ang in range(s_center - 15, s_center + 16, 5):
                    if 0 <= ang <= 180:
                        refine_angles.append(ang)
                refine_s = []
                refine_p = []
                for ang in refine_angles:
                    if self._abort:
                        break
                    if hasattr(self.controller, 'servo_move_calibration_only'):
                        self.controller.servo_move_calibration_only(s=ang, p=(ang + 90) % 180)
                        time.sleep(0.05)
                    s_int = self._read_mode_intensity('s')
                    p_int = self._read_mode_intensity('p')
                    refine_s.append(s_int)
                    refine_p.append(p_int)
                    self.progress.emit({'stage': 'refine', 'angle': ang, 's_intensity': s_int, 'p_intensity': p_int})
                if len(refine_s):
                    s_center = refine_angles[int(np.argmax(refine_s))]

                # ---------------- Stage 3: Fine refinement ----------------
                fine_angles = []
                for ang in range(s_center - 5, s_center + 6, 1):
                    if 0 <= ang <= 180:
                        fine_angles.append(ang)
                fine_s = []
                fine_p = []
                for ang in fine_angles:
                    if self._abort:
                        break
                    if hasattr(self.controller, 'servo_move_calibration_only'):
                        self.controller.servo_move_calibration_only(s=ang, p=(ang + 90) % 180)
                        time.sleep(0.04)
                    s_int = self._read_mode_intensity('s')
                    p_int = self._read_mode_intensity('p')
                    fine_s.append(s_int)
                    fine_p.append(p_int)
                    self.progress.emit({'stage': 'fine', 'angle': ang, 's_intensity': s_int, 'p_intensity': p_int})
                if len(fine_s):
                    s_final = fine_angles[int(np.argmax(fine_s))]
                else:
                    s_final = s_center

                # Determine P candidates ±90
                p_candidate_1 = (s_final + 90) % 180
                p_candidate_2 = (s_final - 90) % 180
                candidates = [p_candidate_1, p_candidate_2]
                p_measurements = {}
                for pc in candidates:
                    if hasattr(self.controller, 'servo_move_calibration_only'):
                        self.controller.servo_move_calibration_only(s=s_final, p=pc)
                        time.sleep(0.05)
                    p_int = self._read_mode_intensity('p')
                    p_measurements[pc] = p_int
                if len(p_measurements) == 0:
                    self.finished.emit({'s_pos': None, 'p_pos': None, 'ratio': None, 'success': False, 'details': 'No P measurements'})
                    return
                p_final = min(p_measurements.keys(), key=lambda k: p_measurements[k])
                # Final ratio measurement
                if hasattr(self.controller, 'servo_move_calibration_only'):
                    self.controller.servo_move_calibration_only(s=s_final, p=p_final)
                    time.sleep(0.05)
                s_int_final = self._read_mode_intensity('s')
                p_int_final = self._read_mode_intensity('p')
                ratio = s_int_final / (p_int_final + 1e-6)
                success = True
                self.finished.emit({
                    's_pos': s_final,
                    'p_pos': p_final,
                    'ratio': ratio,
                    'success': success,
                    'details': {
                        'coarse': {'angles': coarse_angles, 's': coarse_s, 'p': coarse_p},
                        'refine': {'angles': refine_angles, 's': refine_s, 'p': refine_p},
                        'fine': {'angles': fine_angles, 's': fine_s, 'p': fine_p},
                        'p_candidates': p_measurements
                    }
                })
            except Exception as e:
                self.finished.emit({'s_pos': None, 'p_pos': None, 'ratio': None, 'success': False, 'details': f'Exception: {e}'})

    def _run_polarization_scan(self):
        """Start threaded polarization scan calibration."""
        if not self.hardware_ready or not hasattr(self, 'controller') or not hasattr(self, 'usb'):
            self._log("Cannot run scan - hardware not ready")
            return

        if self.is_acquiring:
            self._log("Pausing live acquisition for scan")
            self._stop_acquisition()

        # Quick existing ratio check (skip if already good)
        try:
            existing_s = int(self.servo_s_spin.value())
            existing_p = int(self.servo_p_spin.value())
            if hasattr(self.controller, 'servo_move_calibration_only'):
                self.controller.servo_move_calibration_only(s=existing_s, p=existing_p)
            import time
            time.sleep(0.05)
            # Measure S
            if hasattr(self.controller, 'set_mode'):
                self.controller.set_mode('s')
            time.sleep(0.05)
            spec_s = self.usb.read_intensity() if hasattr(self.usb, 'read_intensity') else None
            s_val = float(np.max(spec_s)) if (spec_s is not None and len(spec_s)>0) else 0.0
            # Measure P
            if hasattr(self.controller, 'set_mode'):
                self.controller.set_mode('p')
            time.sleep(0.05)
            spec_p = self.usb.read_intensity() if hasattr(self.usb, 'read_intensity') else None
            p_val = float(np.max(spec_p)) if (spec_p is not None and len(spec_p)>0) else 0.0
            existing_ratio = s_val / (p_val + 1e-6) if p_val>0 else 0.0
            if existing_ratio >= 1.25 and s_val > 0 and p_val > 0:
                self._log(f"Existing S/P ratio {existing_ratio:.2f} acceptable (>=1.25) → skipping calibration")
                self.calib_status_label.setText(f"Skipped (ratio={existing_ratio:.2f})")
                if not self.is_acquiring and self.auto_start_checkbox.isChecked():
                    self._start_acquisition()
                return
            else:
                self._log(f"Ratio pre-check {existing_ratio:.2f} insufficient → running calibration")
        except Exception as e:
            self._log(f"Ratio pre-check failed: {e}. Proceeding with calibration.")

        # Reset plot data
        self._scan_angles.clear()
        self._scan_s_intensity.clear()
        self._scan_p_intensity.clear()
        self.scan_curve_s.setData([], [])
        self.scan_curve_p.setData([], [])
        self.calib_status_label.setText("Scanning...")
        self.run_calib_button.setEnabled(False)
        self.apply_servo_button.setEnabled(False)

        # Create worker
        self._calibration_worker = self._PolarizationScanWorker(
            controller=self.controller,
            usb=self.usb,
            integration_time=20.0,
            led_channel='a',
            led_intensity= max(80, self.led_intensities.get('a', 0) or 120)
        )
        self._calibration_worker.progress.connect(self._on_scan_progress)
        self._calibration_worker.finished.connect(self._on_scan_finished)
        self._calibration_worker.start()
        self._log("Polarization calibration started (coarse→refine→fine)")

    def _on_scan_progress(self, data: dict):
        angle = data.get('angle')
        s_int = data.get('s_intensity', 0.0)
        p_int = data.get('p_intensity', 0.0)
        stage = data.get('stage', 'coarse')
        # Store only S-mode intensities for plotting against angle; keep both for ratio insight
        self._scan_angles.append(angle)
        self._scan_s_intensity.append(s_int)
        self._scan_p_intensity.append(p_int)
        self.scan_curve_s.setData(self._scan_angles, self._scan_s_intensity)
        self.scan_curve_p.setData(self._scan_angles, self._scan_p_intensity)
        if stage == 'coarse' and angle % 30 == 0:
            self._log(f"Coarse {angle}°: S={s_int:.0f} P={p_int:.0f}")
        elif stage == 'refine' and angle % 5 == 0:
            self._log(f"Refine {angle}°: S={s_int:.0f} P={p_int:.0f}")
        elif stage == 'fine':
            self._log(f"Fine {angle}°: S={s_int:.0f} P={p_int:.0f}")

    def _on_scan_finished(self, result: dict):
        if result.get('success'):
            s_pos = result.get('s_pos')
            p_pos = result.get('p_pos')
            ratio = result.get('ratio')
            self._log(f"Calibration complete → S={s_pos}° P={p_pos}° (S/P ratio={ratio:.2f})")
            self.calib_status_label.setText(f"Done: S={s_pos}° P={p_pos}° (ratio={ratio:.2f})")
            try:
                self.servo_s_spin.setValue(int(s_pos))
                self.servo_p_spin.setValue(int(p_pos))
                self.current_servo_label.setText(f"Current: S={s_pos}° P={p_pos}°")
            except Exception:
                pass
            if self.save_servo_checkbox.isChecked() and hasattr(self, 'device_config') and self.device_config:
                try:
                    self.device_config.set_servo_positions(int(s_pos), int(p_pos))
                    self.device_config.save(auto_sync_eeprom=False)
                    self._log("Saved new S/P positions to device_config.json")
                except Exception as e:
                    self._log(f"Save failed: {e}")
        else:
            self._log(f"Polarization calibration failed ({result.get('details')})")
            self.calib_status_label.setText("Failed")

        self.run_calib_button.setEnabled(True)
        self.apply_servo_button.setEnabled(True)
        # Resume acquisition if previously running desired
        if not self.is_acquiring and self.auto_start_checkbox.isChecked():
            self._start_acquisition()

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
    # Allow running directly: launches the live detector monitor UI
    main()

