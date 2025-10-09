"""SPR System State Machine for simplified hardware and operation management."""

from __future__ import annotations

import time
from enum import Enum
from typing import Any, Optional, Union

from PySide6.QtCore import QObject, QTimer, Signal

from utils.logger import logger

# Import real components first (preferred)
try:
    from utils.hardware_manager import HardwareManager
    from utils.spr_calibrator import SPRCalibrator
    REAL_HARDWARE_AVAILABLE = True
    logger.info("Real hardware components available")
except ImportError:
    REAL_HARDWARE_AVAILABLE = False
    logger.warning("Real hardware components not available")

# Import mock components for fallback testing
try:
    from utils.mock_hardware_manager import MockHardwareManager
    from utils.mock_calibrator import MockCalibrator
    MOCK_MODE_AVAILABLE = True
    logger.info("Mock components available for testing")
except ImportError:
    MOCK_MODE_AVAILABLE = False
    logger.debug("Mock components not available")

# Determine which mode to use (prefer real hardware)
USE_REAL_HARDWARE = REAL_HARDWARE_AVAILABLE

from utils.spr_data_acquisition_simple import SPRDataAcquisition


class SPRSystemState(Enum):
    """Clear system states for SPR operation."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    CALIBRATING = "calibrating"
    CALIBRATED = "calibrated"
    MEASURING = "measuring"
    ERROR = "error"


class SPRStateMachine(QObject):
    """Single state machine to control all SPR operations."""

    # Signals for UI updates
    state_changed = Signal(str)  # Current state
    hardware_status = Signal(bool, bool)  # (ctrl_connected, usb_connected)
    calibration_progress = Signal(int, str)  # (step_number, description)
    calibration_completed = Signal(bool, str)  # (success, error_message)
    data_acquisition_started = Signal()
    error_occurred = Signal(str)  # Error message

    def __init__(self, app: Any) -> None:
        """Initialize the SPR state machine.

        Args:
            app: The main application instance
        """
        super().__init__()
        self.app = app
        self.state = SPRSystemState.DISCONNECTED

        # Hardware and operation managers (use Any to support both real and mock)
        self.hardware_manager: Any = None
        self.calibrator: Any = None
        self.data_acquisition: Optional[SPRDataAcquisition] = None

        # Error tracking
        self.error_count = 0
        self.max_error_count = 3
        self.last_error_time = 0

        # Single timer for all operations
        self.operation_timer = QTimer(self)
        self.operation_timer.timeout.connect(self._process_current_state)
        self.operation_timer.start(100)  # Check every 100ms

        logger.info("SPR State Machine initialized")
        self._emit_state_change()

    def _emit_state_change(self) -> None:
        """Emit state change signal and log transition."""
        logger.info(f"State machine transition to: {self.state.value}")
        self.state_changed.emit(self.state.value)

    def _process_current_state(self) -> None:
        """Single method that handles all state transitions."""
        try:
            if self.state == SPRSystemState.DISCONNECTED:
                self._handle_disconnected()
            elif self.state == SPRSystemState.CONNECTING:
                self._handle_connecting()
            elif self.state == SPRSystemState.CONNECTED:
                self._handle_connected()
            elif self.state == SPRSystemState.CALIBRATING:
                self._handle_calibrating()
            elif self.state == SPRSystemState.CALIBRATED:
                self._handle_calibrated()
            elif self.state == SPRSystemState.MEASURING:
                self._handle_measuring()
            elif self.state == SPRSystemState.ERROR:
                self._handle_error()
        except Exception as e:
            logger.exception(f"Error in state machine: {e}")
            self._transition_to_error(f"State machine error: {e}")

    def _handle_disconnected(self) -> None:
        """Try to discover and connect hardware.""" 
        if not self.hardware_manager:
            logger.debug("Creating hardware manager...")
            # For production use, fall back to mock mode for now
            # This can be extended when the hardware manager is simplified
            if MOCK_MODE_AVAILABLE:
                logger.info("Using mock hardware manager for state machine testing")
                self.hardware_manager = MockHardwareManager()
            else:
                self._transition_to_error("No hardware manager available")
                return

        logger.debug("Attempting hardware discovery...")
        if self.hardware_manager.discover_hardware():
            self._transition_to_state(SPRSystemState.CONNECTING)
        else:
            # Stay in disconnected state, will retry next cycle
            time.sleep(1)  # Brief pause between discovery attempts

    def _handle_connecting(self) -> None:
        """Complete hardware connection."""
        if not self.hardware_manager:
            self._transition_to_error("Hardware manager not available during connection")
            return

        logger.debug("Attempting hardware connection...")
        if self.hardware_manager.connect_all():
            # Sync hardware to app
            self.app.ctrl = self.hardware_manager.ctrl
            self.app.usb = self.hardware_manager.usb
            self.app.knx = self.hardware_manager.knx

            # Update hardware status
            ctrl_ok = self.app.ctrl is not None
            usb_ok = self.app.usb is not None
            self.hardware_status.emit(ctrl_ok, usb_ok)

            self._transition_to_state(SPRSystemState.CONNECTED)
        else:
            self._transition_to_error("Failed to connect to hardware")

    def _handle_connected(self) -> None:
        """Start calibration automatically if not already calibrated."""
        if getattr(self.app, 'calibrated', False):
            logger.info("System already calibrated, skipping to measurement")
            self._transition_to_state(SPRSystemState.CALIBRATED)
            return

        if not self.calibrator:
            logger.debug("Creating calibrator...")
            try:
                if MOCK_MODE_AVAILABLE:
                    logger.info("Using mock calibrator for testing")
                    self.calibrator = MockCalibrator(
                        self.hardware_manager.ctrl,
                        self.hardware_manager.usb
                    )
                    # Connect calibrator progress signals
                    self.calibrator.set_progress_callback(self._on_calibration_progress)
                else:
                    # TODO: Implement real calibrator when hardware manager is simplified
                    self._transition_to_error("Real calibrator not yet integrated with state machine")
                    return
            except Exception as e:
                self._transition_to_error(f"Failed to create calibrator: {e}")
                return

        self._transition_to_state(SPRSystemState.CALIBRATING)

    def _handle_calibrating(self) -> None:
        """Process calibration."""
        if not self.calibrator:
            self._transition_to_error("Calibrator not available during calibration")
            return

        if not hasattr(self.calibrator, '_calibration_started'):
            logger.info("Starting automatic calibration...")
            try:
                # Start calibration in a non-blocking way
                success = self.calibrator.start_calibration()
                self.calibrator._calibration_started = True

                if not success:
                    self._transition_to_error("Failed to start calibration")
                    return
            except Exception as e:
                self._transition_to_error(f"Calibration start error: {e}")
                return

        # Check if calibration is complete
        if self.calibrator.is_complete():
            success = self.calibrator.was_successful()
            error_msg = self.calibrator.get_error_message() if not success else ""

            self.calibration_completed.emit(success, error_msg)

            if success:
                self.app.calibrated = True
                # Store calibration results
                self.app.data_processor = self.calibrator.create_data_processor(
                    med_filt_win=getattr(self.app, 'med_filt_win', 5)
                )
                self.app.leds_calibrated = self.calibrator.state.leds_calibrated.copy()
                self.app.ref_sig = self.calibrator.state.ref_sig.copy()

                self._transition_to_state(SPRSystemState.CALIBRATED)
            else:
                self._transition_to_error(f"Calibration failed: {error_msg}")

    def _handle_calibrated(self) -> None:
        """Start data acquisition."""
        if not self.data_acquisition:
            logger.debug("Creating data acquisition...")
            try:
                self.data_acquisition = SPRDataAcquisition(
                    controller=self.app.ctrl,
                    spectrometer=self.app.usb,
                    data_processor=getattr(self.app, 'data_processor', None),
                    calibrated=True
                )
            except Exception as e:
                self._transition_to_error(f"Failed to create data acquisition: {e}")
                return

        if not self.data_acquisition.is_running():
            logger.info("Starting real-time data acquisition...")
            try:
                self.data_acquisition.start()
                self.data_acquisition_started.emit()
                self._transition_to_state(SPRSystemState.MEASURING)
            except Exception as e:
                self._transition_to_error(f"Failed to start data acquisition: {e}")

    def _handle_measuring(self) -> None:
        """Monitor data acquisition."""
        if not self.data_acquisition:
            self._transition_to_error("Data acquisition not available during measurement")
            return

        if not self.data_acquisition.is_healthy():
            logger.warning("Data acquisition unhealthy, attempting restart...")
            try:
                self.data_acquisition.restart()
            except Exception as e:
                logger.error(f"Failed to restart data acquisition: {e}")
                self._transition_to_error("Data acquisition restart failed")

        # Data acquisition runs continuously in this state
        # The actual data reading is handled by the data acquisition object

    def _handle_error(self) -> None:
        """Handle error state with recovery logic."""
        current_time = time.time()

        # Wait before attempting recovery
        if current_time - self.last_error_time < 2.0:  # Reduced from 5.0 to 2.0 for testing
            return

        if self.error_count < self.max_error_count:
            logger.info(f"Attempting error recovery (attempt {self.error_count + 1}/{self.max_error_count})")
            self._cleanup()
            self.error_count += 1
            self._transition_to_state(SPRSystemState.DISCONNECTED)
        else:
            logger.error("Maximum error recovery attempts reached, staying in error state")
            # Stay in error state - manual intervention required

    def _transition_to_state(self, new_state: SPRSystemState) -> None:
        """Transition to a new state."""
        if self.state != new_state:
            old_state = self.state
            self.state = new_state
            logger.info(f"State transition: {old_state.value} → {new_state.value}")
            self._emit_state_change()

            # Reset error count on successful transition
            if new_state != SPRSystemState.ERROR:
                self.error_count = 0

    def _transition_to_error(self, error_message: str) -> None:
        """Transition to error state with message."""
        logger.error(f"State machine error: {error_message}")
        self.error_occurred.emit(error_message)
        self.last_error_time = time.time()
        self._transition_to_state(SPRSystemState.ERROR)

    def _on_calibration_progress(self, step: int, description: str) -> None:
        """Handle calibration progress updates."""
        logger.debug(f"Calibration progress: Step {step} - {description}")
        self.calibration_progress.emit(step, description)

    def _cleanup(self) -> None:
        """Clean up all resources."""
        logger.debug("Cleaning up state machine resources...")

        if self.data_acquisition:
            try:
                self.data_acquisition.stop()
            except Exception as e:
                logger.error(f"Error stopping data acquisition: {e}")
            self.data_acquisition = None

        if self.calibrator:
            try:
                self.calibrator.stop()
            except Exception as e:
                logger.error(f"Error stopping calibrator: {e}")
            self.calibrator = None

        if self.hardware_manager:
            try:
                self.hardware_manager.disconnect_all()
            except Exception as e:
                logger.error(f"Error disconnecting hardware: {e}")
            # Don't set to None - keep for reconnection

    def stop(self) -> None:
        """Stop the state machine and clean up."""
        logger.info("Stopping SPR state machine...")
        self.operation_timer.stop()
        self._cleanup()
        self.state = SPRSystemState.DISCONNECTED
        self._emit_state_change()

    def force_reconnect(self) -> None:
        """Force a reconnection attempt."""
        logger.info("Forcing hardware reconnection...")
        self._cleanup()
        self._transition_to_state(SPRSystemState.DISCONNECTED)

    def get_current_state(self) -> str:
        """Get the current state as a string."""
        return self.state.value

    def is_measuring(self) -> bool:
        """Check if the system is currently measuring."""
        return self.state == SPRSystemState.MEASURING

    def is_calibrated(self) -> bool:
        """Check if the system is calibrated."""
        return self.state in [SPRSystemState.CALIBRATED, SPRSystemState.MEASURING]

    def is_connected(self) -> bool:
        """Check if hardware is connected."""
        return self.state in [
            SPRSystemState.CONNECTED,
            SPRSystemState.CALIBRATING,
            SPRSystemState.CALIBRATED,
            SPRSystemState.MEASURING
        ]