"""Main Application with State Machine Architecture (with fallback to threading)."""

from __future__ import annotations

import os
import sys
from typing import Any

# ============================================================================
# ADD PARENT DIRECTORY TO PATH FOR DIRECT EXECUTION
# ============================================================================
# When running main.py directly (not through run_app.py), we need to add
# the parent directory to sys.path so imports work correctly
if __name__ == '__main__':
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

# ============================================================================
# CRITICAL: PYTHON VERSION CHECK - MUST BE 3.12+
# ============================================================================
if sys.version_info < (3, 12):
    print("\n" + "=" * 80)
    print("❌ CRITICAL ERROR: WRONG PYTHON VERSION")
    print("=" * 80)
    print(f"   Current Python: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    print(f"   Required: 3.12+")
    print()
    print("   You are using Python 3.9 or earlier, which is NOT compatible!")
    print()
    print("   This will cause errors like:")
    print("   - TypeError: unsupported operand type(s) for |")
    print("   - AttributeError: module 'datetime' has no attribute 'UTC'")
    print()
    print("   SOLUTION:")
    print("   1. Use the launcher: run_app_312.bat or run_app_312.ps1")
    print("   2. Or activate Python 3.12: .venv312\\Scripts\\Activate.ps1")
    print()
    print("   Current Python executable: " + sys.executable)
    print("=" * 80)
    print()

    # Try to show GUI error if possible
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
        app = QApplication(sys.argv)
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle("Python Version Error")
        msg.setText(f"Wrong Python Version: {sys.version_info.major}.{sys.version_info.minor}")
        msg.setInformativeText(
            f"This application requires Python 3.12+\n\n"
            f"Current: {sys.executable}\n\n"
            f"Please use:\n"
            f"• run_app_312.bat\n"
            f"• run_app_312.ps1\n\n"
            f"Or activate .venv312 first"
        )
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec()
    except:
        pass

    sys.exit(1)

from PySide6.QtCore import Slot, QTimer, Signal
from PySide6.QtWidgets import QApplication

from settings import SW_VERSION
from utils.device_configuration import DeviceConfiguration
from utils.logger import logger
from widgets.mainwindow import MainWindow
from widgets.message import show_message

# Environment variable to choose between state machine and threading
# DISABLED BY DEFAULT: State machine causes GUI freezes due to blocking hardware I/O
# Set USE_STATE_MACHINE=true environment variable to enable if needed
USE_STATE_MACHINE = os.getenv('USE_STATE_MACHINE', 'true').lower() == 'true'

if USE_STATE_MACHINE:
    logger.info("Using State Machine Architecture")
    from utils.spr_state_machine import SPRStateMachine

class AffiniteApp(QApplication):
    """Simplified main application using state machine architecture."""

    # Processing diagnostics signal
    processing_steps_signal = Signal(dict)

    def __init__(self) -> None:
        """Initialize the application with state machine architecture."""
        super().__init__(sys.argv)

        # Suppress Qt internal connection warnings (harmless)
        os.environ['QT_LOGGING_RULES'] = '*.debug=false;qt.qpa.*=false'

        # Display Python version banner
        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        logger.warning("=" * 80)
        logger.warning(f"🐍 Python Version: {py_ver}")
        logger.warning(f"📂 Python Executable: {sys.executable}")
        if sys.version_info >= (3, 12):
            logger.warning("✅ Python version OK (3.12+)")
        else:
            logger.warning(f"⚠️  WARNING: Python {py_ver} is NOT the required version!")
            logger.warning("   Expected: Python 3.12+")
            logger.warning("   Use: run_app_312.bat or run_app_312.ps1")
        logger.warning("=" * 80)

        # Load device configuration (optical fiber diameter, LED model, etc.)
        try:
            from utils.device_configuration import get_device_config
            self.device_config = get_device_config()
            fiber_diameter = self.device_config.get_optical_fiber_diameter()
            led_model = self.device_config.get_led_pcb_model()
            logger.info(f"✅ Device config loaded: {fiber_diameter}µm fiber, {led_model} LED")
        except Exception as e:
            logger.error(f"❌ Failed to load device config: {e}")
            # Use default configuration as fallback
            from utils.device_configuration import get_device_config
            self.device_config = get_device_config()
            logger.info("✅ Using default device configuration")

        # Basic attributes (backward compatibility)
        self.calibrated = False
        self.ctrl = None
        self.usb = None
        self.knx = None
        self.data_processor = None
        self.leds_calibrated = {}
        self.ref_sig = {}

        # Initialize main window
        self.main_window = MainWindow(self)

        # Connect device widget signals
        if hasattr(self.main_window, 'sidebar') and hasattr(self.main_window.sidebar, 'device_widget'):
            self.main_window.sidebar.device_widget.connect_dev_sig.connect(self.connect_dev)
            self.main_window.sidebar.device_widget.quick_cal_sig.connect(self.start_calibration)
            logger.debug("Connected device widget signals")

        # Connect spectroscopy tab signals
        if hasattr(self.main_window, 'spectroscopy'):
            self.main_window.spectroscopy.polarizer_sig.connect(self.set_polarizer)
            self.main_window.spectroscopy.single_led_sig.connect(self.single_led)
            logger.debug("Connected spectroscopy signals (polarizer, single LED)")

        # Connect SPR Settings tab signals (reference channel, units, filtering)
        if hasattr(self.main_window, 'sensorgram') and hasattr(self.main_window.sensorgram, 'reference_channel_dlg'):
            # Reference channel and units are already connected via datawindow.py
            # Connect live filtering signal
            try:
                self.main_window.sensorgram.reference_channel_dlg.live_filt_sig.connect(self._on_live_filter_changed)
                logger.debug("Connected live filtering signal")
            except Exception as e:
                logger.warning(f"Could not connect live filter signal: {e}")

            # Connect peak model signal
            try:
                self.main_window.sensorgram.reference_channel_dlg.peak_model_sig.connect(self._on_peak_model_changed)
                logger.debug("Connected peak tracking model signal")
            except Exception as e:
                logger.warning(f"Could not connect peak model signal: {e}")

        if hasattr(self.main_window, 'data_processing') and hasattr(self.main_window.data_processing, 'reference_channel_dlg'):
            # Connect processed data filtering signal
            try:
                self.main_window.data_processing.reference_channel_dlg.proc_filt_sig.connect(self._on_proc_filter_changed)
                logger.debug("Connected processed data filtering signal")
            except Exception as e:
                logger.warning(f"Could not connect proc filter signal: {e}")

            # Connect peak model signal (same handler for both tabs)
            try:
                self.main_window.data_processing.reference_channel_dlg.peak_model_sig.connect(self._on_peak_model_changed)
                logger.debug("Connected peak tracking model signal (processed data tab)")
            except Exception as e:
                logger.warning(f"Could not connect peak model signal: {e}")

        # Set application-wide styling with improved contrast
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #D3D3D3;
            }
            QGroupBox {
                background-color: #D3D3D3;
                border: 1px solid #A0A0A0;
                border-radius: 4px;
                margin-top: 0.5em;
                font-weight: bold;
                color: #000000;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px 0 3px;
                color: #000000;
            }
            QPushButton {
                background-color: #E8E8E8;
                border: 1px solid #A0A0A0;
                border-radius: 3px;
                padding: 5px;
                color: #000000;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #F0F0F0;
            }
            QPushButton:pressed {
                background-color: #C0C0C0;
            }
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
                background-color: #FFFFFF;
                border: 1px solid #A0A0A0;
                border-radius: 3px;
                padding: 3px;
                color: #000000;
            }
            QTableWidget {
                background-color: #FFFFFF;
                gridline-color: #C0C0C0;
                color: #000000;
            }
            QHeaderView::section {
                background-color: #E0E0E0;
                padding: 4px;
                border: 1px solid #A0A0A0;
                color: #000000;
                font-weight: bold;
            }
            QLabel {
                color: #000000;
                background-color: transparent;
            }
            QCheckBox {
                color: #000000;
                background-color: transparent;
            }
            QRadioButton {
                color: #000000;
                background-color: transparent;
            }
            GraphicsLayoutWidget {
                background-color: #FFFFFF;
                border: 1px solid #A0A0A0;
            }
        """)

        if USE_STATE_MACHINE:
            # Initialize state machine
            self.state_machine = SPRStateMachine(self)
            self._setup_state_machine_connections()
            self.architecture = "State Machine"
        else:
            # TODO: Initialize threading architecture
            # This would use the original main_original_threading.py approach
            logger.warning("Threading architecture not yet implemented in hybrid mode")
            self.architecture = "Threading (not implemented)"

        logger.info(f"========== Starting Affinite Instruments Application ({self.architecture}) ==========")
        logger.info(f"Version {SW_VERSION}")

        # Show main window
        self.main_window.show()

        logger.info("AffiniteApp initialized")

        # Auto-connect hardware on startup (if not using state machine)
        if not USE_STATE_MACHINE:
            # Use QTimer to attempt connection after UI is ready
            from PySide6.QtCore import QTimer
            QTimer.singleShot(500, self._auto_connect_hardware)

    def _setup_state_machine_connections(self) -> None:
        """Connect state machine signals to UI updates."""
        if not hasattr(self, 'state_machine'):
            return

        self.state_machine.state_changed.connect(self._on_state_changed)
        self.state_machine.hardware_status.connect(self._on_hardware_status)
        self.state_machine.calibration_progress.connect(self._on_calibration_progress)
        self.state_machine.calibration_completed.connect(self._on_calibration_completed)
        self.state_machine.data_acquisition_started.connect(self._on_data_acquisition_started)
        self.state_machine.error_occurred.connect(self._on_error_occurred)
        # On any error, immediately trigger emergency stop to ensure LEDs are off
        self.state_machine.error_occurred.connect(lambda _msg: self.state_machine.emergency_stop())

    @Slot(str)
    def _on_state_changed(self, state: str) -> None:
        """Handle state machine state changes."""
        logger.info(f"Application state: {state}")

        # Update UI based on state - check if components exist
        if hasattr(self.main_window, 'status_bar') and self.main_window.status_bar:
            self.main_window.status_bar.showMessage(f"System State: {state.upper()}")

        # Update connection indicators
        if state in ["connected", "calibrating", "calibrated", "measuring"]:
            self._update_connection_display(True)
        else:
            self._update_connection_display(False)

    @Slot(bool, bool)
    def _on_hardware_status(self, ctrl_connected: bool, usb_connected: bool) -> None:
        """Handle hardware connection status updates."""
        logger.info(f"Hardware status - Controller: {ctrl_connected}, Spectrometer: {usb_connected}")

        # Update device widgets if they exist
        if hasattr(self.main_window, 'device_widget'):
            # Update device widget status
            pass

        # Update device indicator (blue box, bottom-left)
        try:
            if ctrl_connected:
                # Pico P4SPR controller present -> show SPR
                self.main_window.ui.device.setText("SPR")
            elif usb_connected:
                # Only spectrometer connected
                self.main_window.ui.device.setText("SPEC")
            else:
                self.main_window.ui.device.setText("No Devices")
        except Exception:
            pass

    @Slot(int, str)
    def _on_calibration_progress(self, step: int, description: str) -> None:
        """Handle calibration progress updates."""
        logger.info(f"Calibration progress: Step {step} - {description}")

        # Update progress bar if it exists
        if hasattr(self.main_window, 'ui') and hasattr(self.main_window.ui, 'calibration_progress'):
            progress_bar = self.main_window.ui.calibration_progress
            # Make progress bar visible during calibration
            progress_bar.setVisible(True)
            # Calculate percentage (assuming 9 steps)
            percentage = int((step / 9) * 100)
            progress_bar.setValue(percentage)
            progress_bar.setFormat(f"Step {step}/9: {description}")
            logger.debug(f"Updated progress bar: {percentage}% - {description}")
        else:
            logger.debug("Progress bar not found in UI")

    @Slot(bool, str)
    def _on_calibration_completed(self, success: bool, error_message: str) -> None:
        """Handle calibration completion."""
        if success:
            logger.info("✅ Calibration completed successfully")
            show_message("Calibration completed successfully!", msg_type="Information")

            # Update UI to show calibrated state
            if hasattr(self.main_window, 'ui') and hasattr(self.main_window.ui, 'calibration_progress'):
                progress_bar = self.main_window.ui.calibration_progress
                progress_bar.setValue(100)
                progress_bar.setFormat("Calibration Complete!")
                # Hide progress bar after a delay
                QTimer.singleShot(3000, lambda: progress_bar.setVisible(False))
        else:
            logger.error(f"❌ Calibration failed: {error_message}")
            show_message(f"Calibration failed: {error_message}", msg_type="Critical")

            # Hide progress bar on failure
            if hasattr(self.main_window, 'ui') and hasattr(self.main_window.ui, 'calibration_progress'):
                self.main_window.ui.calibration_progress.setVisible(False)

    @Slot()
    def _on_data_acquisition_started(self) -> None:
        """Handle data acquisition start."""
        logger.info("🔄 Real-time data acquisition started")
        show_message("Real-time measurements started!", msg_type="Information")

        # Update UI to show measuring state via status label
        if hasattr(self.main_window, 'ui') and hasattr(self.main_window.ui, 'status'):
            self.main_window.ui.status.setText("MEASURING - Real-time data acquisition active")

    @Slot(str)
    def _on_error_occurred(self, error_message: str) -> None:
        """Handle system errors."""
        logger.error(f"System error: {error_message}")
        show_message(f"System error: {error_message}", msg_type="Warning")

    def _update_connection_display(self, connected: bool) -> None:
        """Update connection display in UI."""
        if hasattr(self.main_window, 'connection_indicator'):
            # Update connection indicator
            pass

    def _auto_connect_hardware(self) -> None:
        """Attempt to auto-connect hardware on startup (non-state-machine mode)."""
        if USE_STATE_MACHINE:
            return  # State machine handles this

        logger.info("🔍 Auto-detecting hardware on startup...")
        self.main_window.ui.status.setText("Auto-detecting hardware...")

        try:
            from utils.hal.hal_factory import HALFactory

            # Try controller
            try:
                self.ctrl = HALFactory.create_controller(device_type="PicoP4SPR", auto_detect=True)
                logger.info("✅ Auto-detected controller")
            except Exception as e:
                logger.info(f"Controller not found: {e}")
                self.ctrl = None

            # Try spectrometer
            try:
                self.usb = HALFactory.create_spectrometer(auto_detect=True)
                logger.info("✅ Auto-detected spectrometer")
            except Exception as e:
                logger.info(f"Spectrometer not found: {e}")
                self.usb = None

            # If hardware found, auto-start workflow
            if self.ctrl and self.usb:
                logger.info("🎯 Hardware found! Starting automatic workflow...")
                self._update_device_config()
                self.main_window.ui.status.setText("Hardware connected - Starting calibration...")
                # Update device label to SPR when controller present
                try:
                    self.main_window.ui.device.setText("SPR")
                except Exception:
                    pass
                self.start_calibration()
            else:
                logger.info("No hardware found on startup - waiting for manual connection")
                self.main_window.ui.status.setText("No hardware detected - Click 'Add SPR Device' to connect")
                try:
                    # Show SPEC if only spectrometer is detected
                    if self.usb and not self.ctrl:
                        self.main_window.ui.device.setText("SPEC")
                    else:
                        self.main_window.ui.device.setText("No Devices")
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Auto-connect error: {e}")
            self.main_window.ui.status.setText("Auto-connect failed - Click 'Add SPR Device' to try again")

    # ========================================
    # BACKWARD COMPATIBILITY METHODS
    # ========================================

    @Slot()
    def connect_dev(self) -> None:
        """Connect to devices."""
        logger.info("Manual device connection requested")

        if USE_STATE_MACHINE:
            # State machine mode
            if self.state_machine.get_current_state() == "error":
                self.state_machine.force_reconnect()
            else:
                logger.info("State machine is already handling device connection")
        else:
            # Threading mode - manually connect hardware
            if self.ctrl is not None and self.usb is not None:
                logger.info("Hardware already connected")
                return

            logger.info("Starting hardware connection...")
            self.main_window.ui.status.setText("Scanning for devices...")

            try:
                # Use HAL factory to connect hardware
                from utils.hal.hal_factory import HALFactory

                # Try to connect controller
                if self.ctrl is None:
                    try:
                        logger.info("Attempting to connect PicoP4SPR controller...")
                        self.ctrl = HALFactory.create_controller(
                            device_type="PicoP4SPR",
                            auto_detect=True
                        )
                        logger.info(f"✅ Controller connected: {self.ctrl.get_device_info()}")
                    except Exception as e:
                        logger.error(f"Controller connection failed: {e}")
                        self.ctrl = None

                # Try to connect spectrometer
                if self.usb is None:
                    try:
                        logger.info("Attempting to connect USB4000 spectrometer...")
                        self.usb = HALFactory.create_spectrometer(auto_detect=True)
                        logger.info(f"✅ Spectrometer connected")
                    except Exception as e:
                        logger.error(f"Spectrometer connection failed: {e}")
                        self.usb = None

                # Update UI
                logger.info(f"Hardware connection status - ctrl: {self.ctrl is not None}, usb: {self.usb is not None}")
                if self.ctrl or self.usb:
                    logger.info("Updating device configuration...")
                    self._update_device_config()
                    logger.info("Device configuration updated")
                    self.main_window.ui.status.setText("Hardware connected - Starting calibration...")
                    logger.info(f"🔌 Hardware connected - Controller: {self.ctrl is not None}, Spectrometer: {self.usb is not None}")

                    # Auto-start calibration after connection
                    logger.info("🎯 Auto-starting calibration...")
                    self.start_calibration()
                else:
                    self.main_window.ui.status.setText("No devices found")
                    logger.warning("No hardware devices found")

            except Exception as e:
                logger.exception(f"Error during hardware connection: {e}")
                self.main_window.ui.status.setText(f"Connection error: {str(e)}")

    def _update_device_config(self) -> None:
        """Update device configuration display."""
        ctrl_type = ""
        if self.ctrl is not None:
            if hasattr(self.ctrl, 'device_name'):
                ctrl_type = "PicoP4SPR"
                logger.info(f"✅ Setting device widget to show PicoP4SPR")

        # Update device widget
        if hasattr(self.main_window, 'sidebar') and hasattr(self.main_window.sidebar, 'device_widget'):
            logger.info(f"Calling device_widget.setup with ctrl_type='{ctrl_type}'")
            self.main_window.sidebar.device_widget.setup(ctrl_type, "", None)
            logger.info("Device widget setup completed")
        else:
            logger.error("❌ sidebar.device_widget not found!")

    def start_calibration(self) -> None:
        """Start calibration process."""
        logger.info("🎯 Calibration requested by user")

        if USE_STATE_MACHINE:
            # State machine handles calibration
            logger.info("Requesting calibration from state machine")
            self.state_machine.start_calibration()
        else:
            # Manual calibration - run in background thread
            if self.ctrl is None or self.usb is None:
                logger.error("Cannot calibrate - hardware not connected")
                self.main_window.ui.status.setText("Cannot calibrate - connect hardware first")
                return

            logger.info("Starting manual calibration...")
            self.main_window.ui.status.setText("Calibrating...")

            try:
                # Use SPRCalibrator with HAL hardware
                from utils.spr_calibrator import SPRCalibrator, CalibrationState
                from PySide6.QtCore import QThread

                # Create shared calibration state
                if not hasattr(self, 'calib_state'):
                    self.calib_state = CalibrationState()
                    logger.info("Created shared CalibrationState")

                # Create calibrator
                logger.info("Creating SPRCalibrator...")

                # Use device_config (single source of truth)
                if hasattr(self, 'device_config') and self.device_config:
                    device_config_dict = self.device_config.to_dict() if hasattr(self.device_config, 'to_dict') else {}
                    logger.info(f"✅ Using device_config (single source of truth)")

                    # Debug: Check if OEM calibration is present
                    if 'oem_calibration' in device_config_dict:
                        oem = device_config_dict['oem_calibration']
                        logger.info(f"✅ OEM calibration found: S={oem.get('polarizer_s_position')}, P={oem.get('polarizer_p_position')}")
                    else:
                        logger.warning("⚠️ No 'oem_calibration' section in device_config")
                else:
                    logger.error("❌ No device_config found - this should not happen!")
                    self.main_window.ui.status.setText("Error: No device configuration")
                    return

                self.calibrator = SPRCalibrator(
                    ctrl=self.ctrl,  # type: ignore - HAL is compatible with legacy interface
                    usb=self.usb,  # type: ignore
                    device_type="PicoP4SPR",
                    calib_state=self.calib_state,
                    device_config=device_config_dict
                )

                # Run calibration in background thread
                logger.info("✅ Running calibration in background thread (GUI stays responsive)")

                class CalibrationWorker(QThread):
                    def __init__(self, calibrator):
                        super().__init__()
                        self.calibrator = calibrator
                        self.success = False

                    def run(self):
                        try:
                            self.success = self.calibrator.start_calibration()
                        except Exception as e:
                            logger.exception(f"Calibration thread error: {e}")
                            self.success = False

                def on_calibration_complete():
                    if self.calib_worker.success:
                        logger.info("✅ Calibration completed successfully!")
                        self.calibrated = True
                        self.main_window.ui.status.setText("Calibration complete - Ready to measure")

                        # Show popup stating calibration is done and starting measurements
                        from PySide6.QtWidgets import QMessageBox
                        from PySide6.QtCore import QTimer

                        def show_start_measurement_dialog():
                            msg = QMessageBox(self.main_window)
                            msg.setIcon(QMessageBox.Information)
                            msg.setWindowTitle("Calibration Complete")
                            msg.setText("Calibration done. Starting measurements.")
                            msg.setStandardButtons(QMessageBox.Ok)
                            msg.exec()

                            logger.info("🚀 Starting live measurements after calibration")
                            # TODO: Start live measurements
                            # For now, just update status
                            self.main_window.ui.status.setText("Starting live measurements...")
                            logger.info("Live measurement start not yet implemented in manual mode")
                            logger.info("Please use the state machine mode (USE_STATE_MACHINE=true) for full functionality")
                            self.main_window.ui.status.setText("Ready to measure - Full acquisition requires state machine mode")

                        # Delay popup slightly so calibration logs finish
                        QTimer.singleShot(500, show_start_measurement_dialog)
                    else:
                        logger.error("❌ Calibration failed")
                        self.main_window.ui.status.setText("Calibration failed")

                self.calib_worker = CalibrationWorker(self.calibrator)
                self.calib_worker.finished.connect(on_calibration_complete)
                self.calib_worker.start()

            except Exception as e:
                logger.exception(f"Calibration error: {e}")
                self.main_window.ui.status.setText(f"Calibration error: {str(e)}")

    def get_system_status(self) -> str:
        """Get current system status."""
        return self.state_machine.get_current_state()

    def is_measuring(self) -> bool:
        """Check if system is measuring."""
        return self.state_machine.is_measuring()

    def is_calibrated(self) -> bool:
        """Check if system is calibrated."""
        return self.state_machine.is_calibrated()

    def is_connected(self) -> bool:
        """Check if hardware is connected."""
        return self.state_machine.is_connected()

    # ========================================
    # SPECTROSCOPY CONTROLS
    # ========================================

    def set_polarizer(self, pos: str) -> None:
        """Set polarizer position (S or P mode).

        Args:
            pos: Position string ('s' or 'p')
        """
        logger.info(f"Polarizer position requested: {pos}")

        if USE_STATE_MACHINE and hasattr(self, 'state_machine'):
            # Use state machine to set polarizer
            self.state_machine.set_polarizer_mode(pos)
        elif self.ctrl is not None:
            # Direct hardware control (legacy mode)
            try:
                if 's' in pos.lower():
                    self.ctrl.set_mode(mode='s')
                    logger.info("Polarizer set to S-mode")
                else:
                    self.ctrl.set_mode(mode='p')
                    logger.info("Polarizer set to P-mode")
            except Exception as e:
                logger.error(f"Failed to set polarizer: {e}")
        else:
            logger.warning("Cannot set polarizer - no hardware control available")

    def single_led(self, led_setting: str) -> None:
        """Control single LED mode.

        Args:
            led_setting: LED channel ('a', 'b', 'c', 'd', 'x' for off, 'auto' for normal mode)
        """
        logger.info(f"Single LED mode requested: {led_setting}")

        if USE_STATE_MACHINE and hasattr(self, 'state_machine'):
            # Use state machine to control LEDs
            if led_setting == "auto":
                self.state_machine.set_single_led_mode(False, 'x')
                logger.info("Single LED mode: OFF (auto mode)")
            elif led_setting in ['a', 'b', 'c', 'd']:
                self.state_machine.set_single_led_mode(True, led_setting)
                logger.info(f"Single LED mode: Channel {led_setting.upper()}")
            else:  # 'x' or other
                self.state_machine.set_single_led_mode(True, 'x')
                logger.info("Single LED mode: All LEDs OFF")
        else:
            # Legacy direct control
            logger.warning("Single LED control not implemented in legacy mode")

    # ========================================
    # APPLICATION LIFECYCLE
    # ========================================

    def closeEvent(self, event) -> None:
        """Handle application close."""
        logger.info("Application closing...")

        # Check if LED health monitoring is due (every 100 operating hours)
        try:
            from utils.led_health_monitor import check_and_run_health_monitor
            health_check_ran = check_and_run_health_monitor()
            if health_check_ran:
                logger.info("✅ LED health check completed during shutdown")
        except Exception as e:
            logger.warning(f"LED health check failed during shutdown: {e}")

        self._emergency_cleanup()
        event.accept()

    def _emergency_cleanup(self) -> None:
        """Emergency cleanup to ensure hardware safety."""
        try:
            logger.info("🚨 Emergency cleanup started...")

            # 1. Emergency LED shutdown via state machine
            if hasattr(self, 'state_machine'):
                try:
                    self.state_machine.emergency_stop()
                except Exception as e:
                    logger.error(f"State machine emergency stop failed: {e}")

            # 2. Direct hardware emergency shutdown
            try:
                self._direct_hardware_emergency_shutdown()
            except Exception as e:
                logger.error(f"Direct hardware emergency shutdown failed: {e}")

            # 3. Properly close hardware connections to release COM ports
            try:
                if hasattr(self, 'ctrl') and self.ctrl:
                    if hasattr(self.ctrl, 'disconnect'):
                        self.ctrl.disconnect()
                        logger.info("Controller disconnected")
                    elif hasattr(self.ctrl, '_ser') and self.ctrl._ser:
                        if self.ctrl._ser.is_open:
                            self.ctrl._ser.close()
                            logger.info("Controller serial port closed")

                if hasattr(self, 'usb') and self.usb:
                    if hasattr(self.usb, 'disconnect'):
                        self.usb.disconnect()
                        logger.info("Spectrometer disconnected")
            except Exception as e:
                logger.warning(f"Hardware disconnect failed: {e}")

            # 4. Stop state machine
            if hasattr(self, 'state_machine'):
                try:
                    self.state_machine.stop()
                except Exception as e:
                    logger.error(f"State machine stop failed: {e}")

            # 5. Close main window
            if hasattr(self, 'main_window'):
                try:
                    self.main_window.close()
                except Exception as e:
                    logger.error(f"Main window close failed: {e}")

            logger.info("✅ Emergency cleanup completed")

        except Exception as e:
            logger.error(f"❌ Emergency cleanup failed: {e}")

    def _direct_hardware_emergency_shutdown(self) -> None:
        """Direct hardware emergency shutdown bypassing all abstractions."""
        import serial
        import time

        try:
            logger.info("🔥 Direct hardware emergency shutdown...")

            # First try: Use existing hardware connection if available
            shutdown_success = False

            # Check state machine controller
            if hasattr(self, 'state_machine') and hasattr(self.state_machine, 'ctrl'):
                try:
                    ctrl = self.state_machine.ctrl
                    if ctrl and hasattr(ctrl, '_ser') and ctrl._ser and ctrl._ser.is_open:
                        logger.info("Using existing serial connection (state machine) for emergency shutdown")
                        ctrl._ser.write(b'lx\n')  # LED off command
                        time.sleep(0.05)
                        ctrl._ser.write(b'i0\n')  # Intensity zero
                        time.sleep(0.05)
                        logger.info("✅ Emergency shutdown via state machine connection")
                        shutdown_success = True
                except Exception as e:
                    logger.debug(f"State machine emergency shutdown failed: {e}")

            # Check direct controller (non-state-machine mode)
            if not shutdown_success and hasattr(self, 'ctrl') and self.ctrl:
                try:
                    if hasattr(self.ctrl, '_ser') and self.ctrl._ser and self.ctrl._ser.is_open:
                        logger.info("Using existing serial connection (direct ctrl) for emergency shutdown")
                        self.ctrl._ser.write(b'lx\n')  # LED off command
                        time.sleep(0.05)
                        self.ctrl._ser.write(b'i0\n')  # Intensity zero
                        time.sleep(0.05)
                        logger.info("✅ Emergency shutdown via direct controller connection")
                        shutdown_success = True
                    elif hasattr(self.ctrl, 'all_off'):
                        # Use HAL method
                        self.ctrl.all_off()
                        logger.info("✅ Emergency shutdown via HAL all_off()")
                        shutdown_success = True
                except Exception as e:
                    logger.debug(f"Direct controller emergency shutdown failed: {e}")

            # Only try direct COM4 access if all other methods failed
            if not shutdown_success:
                try:
                    with serial.Serial("COM4", 115200, timeout=0.5) as ser:
                        time.sleep(0.05)
                        ser.write(b'lx\n')  # LED off command
                        time.sleep(0.05)
                        ser.write(b'i0\n')  # Intensity zero
                        time.sleep(0.05)
                        logger.info("✅ Emergency shutdown via direct COM4")
                        shutdown_success = True
                except PermissionError:
                    # COM port in use - this is actually GOOD, means hardware is properly connected
                    logger.debug("ℹ️ COM4 in use (normal - hardware still connected)")
                except Exception as e:
                    logger.debug(f"Direct COM4 access skipped: {e}")

            if not shutdown_success:
                logger.info("ℹ️ Emergency shutdown note: No active hardware connection found")

        except Exception as e:
            logger.error(f"Direct hardware shutdown failed: {e}")

    def _on_live_filter_changed(self, enabled: bool, window_size: int) -> None:
        """Handle live filtering setting changes from SPR Settings tab."""
        try:
            logger.info(f"Live filter changed: enabled={enabled}, window={window_size}")
            # Update settings module if available
            try:
                from settings import settings as app_settings
                app_settings.FILTERING_ON = enabled
                app_settings.MED_FILT_WIN = window_size
                logger.debug(f"Updated settings: FILTERING_ON={enabled}, MED_FILT_WIN={window_size}")
            except Exception as e:
                logger.warning(f"Could not update settings module: {e}")

            # TODO: Apply filter to live data acquisition if active
            # For now, this will take effect on next measurement cycle
        except Exception as e:
            logger.error(f"Error handling live filter change: {e}")

    def _on_proc_filter_changed(self, enabled: bool, window_size: int) -> None:
        """Handle processed data filtering setting changes from SPR Settings tab."""
        try:
            logger.info(f"Processed data filter changed: enabled={enabled}, window={window_size}")
            # Update settings module if available
            try:
                from settings import settings as app_settings
                app_settings.FILTERING_ON = enabled
                app_settings.MED_FILT_WIN = window_size
                logger.debug(f"Updated settings for processed data: FILTERING_ON={enabled}, MED_FILT_WIN={window_size}")
            except Exception as e:
                logger.warning(f"Could not update settings module: {e}")

            # The data processing window will apply these settings when reprocessing data
        except Exception as e:
            logger.error(f"Error handling proc filter change: {e}")

    def _on_peak_model_changed(self, model: str) -> None:
        """Handle peak tracking model changes from SPR Settings tab.

        Args:
            model: "old" for numerical derivative, "centroid" for physics-aware
        """
        try:
            logger.info(f"Peak tracking model changed to: {model}")
            # Update settings module (already done in channelmenu, but verify)
            try:
                from settings import settings as app_settings
                if model == "old":
                    app_settings.WIDTH_BIAS_CORRECTION_ENABLED = False
                    app_settings.PEAK_TRACKING_METHOD = 'numerical_derivative'
                    logger.info("✅ Using OLD peak tracker (numerical derivative)")
                elif model == "centroid":
                    app_settings.WIDTH_BIAS_CORRECTION_ENABLED = True
                    # PEAK_TRACKING_METHOD stays 'numerical_derivative' as fallback
                    logger.info("✅ Using CENTROID peak tracker (physics-aware)")
            except Exception as e:
                logger.warning(f"Could not update settings module: {e}")

            # Update data processor if it exists and has the setting
            if hasattr(self, 'state_machine') and self.state_machine and hasattr(self.state_machine, 'data_processor'):
                try:
                    # The data processor uses settings.WIDTH_BIAS_CORRECTION_ENABLED
                    # internally, so just log the change
                    logger.debug(f"Data processor will use {model} peak tracking on next measurement")
                except Exception as e:
                    logger.debug(f"Data processor note: {e}")
        except Exception as e:
            logger.error(f"Error handling peak model change: {e}")

    def close(self) -> None:
        """Close the application (backward compatibility)."""
        self._emergency_cleanup()
        self.quit()


def main() -> None:
    """Main application entry point."""
    import signal

    # Global emergency shutdown function for signal handlers
    def signal_emergency_shutdown(signum, frame):
        """Handle termination signals with emergency shutdown."""
        print(f"\n🚨 Signal {signum} received - Shutting down gracefully...")

        # Try to use the app's cleanup if available
        try:
            if 'app' in locals() or 'app' in globals():
                app_instance = locals().get('app') or globals().get('app')
                if app_instance and hasattr(app_instance, '_emergency_cleanup'):
                    app_instance._emergency_cleanup()
                    print("✅ App emergency cleanup completed")
        except Exception as e:
            print(f"App cleanup failed: {e}")

        # Direct LED shutdown as fallback
        try:
            import serial
            import time
            with serial.Serial("COM4", 115200, timeout=0.5) as ser:
                time.sleep(0.05)
                ser.write(b'lx\n')
                time.sleep(0.05)
                ser.write(b'i0\n')
                time.sleep(0.05)
                print("✅ Emergency LED shutdown completed")
        except PermissionError:
            # COM port in use - this is normal, main app will handle shutdown
            pass
        except Exception as e:
            print(f"ℹ️ Emergency LED shutdown note: {e}")

        # Let Python clean up normally - DON'T force kill
        print("Exiting gracefully...")
        sys.exit(0)

    # Install signal handlers for various termination scenarios
    try:
        signal.signal(signal.SIGINT, signal_emergency_shutdown)   # Ctrl+C
        signal.signal(signal.SIGTERM, signal_emergency_shutdown)  # Termination request
        if hasattr(signal, 'SIGBREAK'):  # Windows specific
            signal.signal(signal.SIGBREAK, signal_emergency_shutdown)  # Ctrl+Break
        logger.info("✅ Emergency shutdown signal handlers installed")
    except Exception as e:
        logger.warning(f"Could not install signal handlers: {e}")

    try:
        # Create and run application
        app = AffiniteApp()

        # Set application properties
        app.setApplicationName("Affinite Instruments SPR")
        app.setApplicationVersion(SW_VERSION)
        app.setOrganizationName("Affinite Instruments")

        # Run application
        exit_code = app.exec()

        logger.info(f"Application exited with code: {exit_code}")
        sys.exit(exit_code)

    except Exception as e:
        logger.exception(f"Fatal application error: {e}")
        # Emergency LED shutdown on crash
        try:
            import serial
            import time
            with serial.Serial("COM4", 115200, timeout=1) as ser:
                time.sleep(0.1)
                ser.write(b'lx\n')
                time.sleep(0.1)
                ser.write(b'i0\n')
                time.sleep(0.1)
                logger.info("Emergency LED shutdown on crash completed")
        except Exception as led_error:
            logger.error(f"Emergency LED shutdown on crash failed: {led_error}")
        sys.exit(1)


if __name__ == "__main__":
    main()