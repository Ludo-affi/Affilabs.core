"""Main Application with State Machine Architecture (with fallback to threading)."""

from __future__ import annotations

import os
import sys
from typing import Any

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QApplication

from settings import SW_VERSION
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

    def __init__(self) -> None:
        """Initialize the application with state machine architecture."""
        super().__init__(sys.argv)

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
        if hasattr(self.main_window, 'progress_bar') and self.main_window.progress_bar:
            # Calculate percentage (assuming 9 steps)
            percentage = int((step / 9) * 100)
            self.main_window.progress_bar.setValue(percentage)
            self.main_window.progress_bar.setFormat(f"{percentage}% - {description}")

    @Slot(bool, str)
    def _on_calibration_completed(self, success: bool, error_message: str) -> None:
        """Handle calibration completion."""
        if success:
            logger.info("✅ Calibration completed successfully")
            show_message("Calibration completed successfully!", msg_type="Information")

            # Update UI to show calibrated state
            if hasattr(self.main_window, 'progress_bar') and self.main_window.progress_bar:
                self.main_window.progress_bar.setValue(100)
                self.main_window.progress_bar.setFormat("100% - Calibration Complete")
        else:
            logger.error(f"❌ Calibration failed: {error_message}")
            show_message(f"Calibration failed: {error_message}", msg_type="Critical")

    @Slot()
    def _on_data_acquisition_started(self) -> None:
        """Handle data acquisition start."""
        logger.info("🔄 Real-time data acquisition started")
        show_message("Real-time measurements started!", msg_type="Information")

        # Update UI to show measuring state
        if hasattr(self.main_window, 'status_bar') and self.main_window.status_bar:
            self.main_window.status_bar.showMessage("System State: MEASURING - Real-time data acquisition active")

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

        # Stop state machine
        if hasattr(self, 'state_machine'):
            self.state_machine.stop()

        # Close main window
        if hasattr(self, 'main_window'):
            self.main_window.close()

        event.accept()


def main() -> None:
    """Main application entry point."""
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
        sys.exit(1)


if __name__ == "__main__":
    main()