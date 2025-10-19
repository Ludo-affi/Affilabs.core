"""Main Application with State Machine Architecture (with fallback to threading)."""

from __future__ import annotations

import os
import sys
from typing import Any

from PySide6.QtCore import Slot, QTimer, Signal
from PySide6.QtWidgets import QApplication

from settings import SW_VERSION
from utils.device_configuration import DeviceConfiguration
from utils.logger import logger
from widgets.mainwindow import MainWindow
from widgets.message import show_message

# Environment variable to choose between state machine and threading
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

        # Set application-wide styling with improved contrast
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #D3D3D3;
            }
            QGroupBox {
                background-color: #C8C8C8;
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
            }
            QCheckBox {
                color: #000000;
            }
            QRadioButton {
                color: #000000;
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

    # ========================================
    # BACKWARD COMPATIBILITY METHODS
    # ========================================

    @Slot()
    def connect_dev(self) -> None:
        """Connect to devices (simplified - state machine handles this automatically)."""
        logger.info("Manual device connection requested")
        if self.state_machine.get_current_state() == "error":
            self.state_machine.force_reconnect()
        else:
            logger.info("State machine is already handling device connection")

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
    # APPLICATION LIFECYCLE
    # ========================================

    def closeEvent(self, event) -> None:
        """Handle application close."""
        logger.info("Application closing...")
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

            # 3. Stop state machine
            if hasattr(self, 'state_machine'):
                try:
                    self.state_machine.stop()
                except Exception as e:
                    logger.error(f"State machine stop failed: {e}")

            # 4. Close main window
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

            # Try to send LED off command directly to COM4
            try:
                with serial.Serial("COM4", 115200, timeout=1) as ser:
                    time.sleep(0.1)
                    # Primary: all LEDs off
                    ser.write(b'lx\n')  # LED off command
                    time.sleep(0.1)
                    # Backup: ensure intensity is zero
                    ser.write(b'i0\n')
                    time.sleep(0.1)
                    response = ser.read(10)
                    logger.info(f"Direct LED shutdown: {response}")
            except Exception as e:
                logger.warning(f"Direct COM4 shutdown failed: {e}")

        except Exception as e:
            logger.error(f"Direct hardware shutdown failed: {e}")

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
        print(f"\n🚨 Signal {signum} received - Emergency shutdown!")

        # Direct LED shutdown for immediate safety
        try:
            import serial
            import time
            with serial.Serial("COM4", 115200, timeout=1) as ser:
                time.sleep(0.1)
                ser.write(b'lx\n')
                time.sleep(0.1)
                ser.write(b'i0\n')
                time.sleep(0.1)
                print("✅ Emergency LED shutdown completed")
        except Exception as e:
            print(f"❌ Emergency LED shutdown failed: {e}")

        sys.exit(1)

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