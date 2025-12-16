from __future__ import annotations

import threading
import time
from collections.abc import Callable

from utils.logger import logger


class ThreadManager:
    """Manages background thread lifecycle and coordination.

    Handles thread startup, shutdown, and cleanup for the main application.
    Coordinates data acquisition, calibration, and connection threads.
    """

    def __init__(
        self,
        *,
        # Thread targets
        data_acquisition_target: Callable[[], None],
        calibration_target: Callable[[], None],
        # Thread control flags
        data_kill_flag: threading.Event,
        calibration_kill_flag: threading.Event,
        sensor_kill_flag: threading.Event,
        # Status callback
        status_callback: Callable[[str], None] | None = None,
    ) -> None:
        # Thread targets
        self.data_acquisition_target = data_acquisition_target
        self.calibration_target = calibration_target

        # Control flags
        self.data_kill_flag = data_kill_flag
        self.calibration_kill_flag = calibration_kill_flag
        self.sensor_kill_flag = sensor_kill_flag

        # Status callback
        self.status_callback = status_callback

        # Thread references
        self.data_thread: threading.Optional[Thread] = None
        self.calibration_thread: threading.Optional[Thread] = None
        self.connection_thread: threading.Optional[Thread] = None
        self.new_signal_thread: threading.Optional[Thread] = None

        # Sensor thread removed (obsolete flow sensors)

    def start_threads(self) -> None:
        """Start all background threads."""
        try:
            logger.debug("Starting background threads")

            # Data acquisition thread
            self.data_thread = threading.Thread(
                target=self.data_acquisition_target,
                daemon=True,
            )
            self.data_thread.start()

            # Calibration thread
            self.calibration_thread = threading.Thread(
                target=self.calibration_target,
                daemon=True,
            )
            self.calibration_thread.start()

            # Placeholder threads (may be used for connection later)
            self.connection_thread = threading.Thread(target=lambda: None, daemon=True)
            self.new_signal_thread = threading.Thread(target=lambda: None, daemon=True)

            logger.info("Background threads started successfully")

        except Exception as e:
            logger.exception(f"Error starting threads: {e}")
            if self.status_callback:
                self.status_callback("Thread startup error")

    def stop_threads(self) -> None:
        """Stop all background threads gracefully."""
        try:
            logger.debug("Stopping background threads")

            # Set kill flags
            self.data_kill_flag.set()
            self.calibration_kill_flag.set()
            self.sensor_kill_flag.set()  # Set even though sensor thread removed

            # Brief pause for threads to respond
            time.sleep(0.5)

            # Join threads with timeout
            if self.calibration_thread and self.calibration_thread.is_alive():
                self.calibration_thread.join(0.5)
                logger.debug("Calibration thread joined")

            if self.data_thread and self.data_thread.is_alive():
                self.data_thread.join(0.5)
                logger.debug("Data acquisition thread joined")

            if self.connection_thread and self.connection_thread.is_alive():
                self.connection_thread.join(0.1)
                logger.debug("Connection thread joined")

            # Note: Sensor reading thread removed (obsolete flow sensors)

            logger.info("Background threads stopped successfully")

        except Exception as e:
            logger.exception(f"Error stopping threads: {e}")

    def is_data_thread_alive(self) -> bool:
        """Check if data acquisition thread is running."""
        return self.data_thread is not None and self.data_thread.is_alive()

    def is_calibration_thread_alive(self) -> bool:
        """Check if calibration thread is running."""
        return (
            self.calibration_thread is not None and self.calibration_thread.is_alive()
        )

    def is_connection_thread_alive(self) -> bool:
        """Check if connection thread is running."""
        return self.connection_thread is not None and self.connection_thread.is_alive()

    def restart_connection_thread(self, target: Callable[[], None]) -> None:
        """Restart connection thread with new target."""
        try:
            # Stop existing connection thread
            if self.connection_thread and self.connection_thread.is_alive():
                self.connection_thread.join(0.1)

            # Start new connection thread
            self.connection_thread = threading.Thread(target=target, daemon=True)
            self.connection_thread.start()

            logger.debug("Connection thread restarted")

        except Exception as e:
            logger.exception(f"Error restarting connection thread: {e}")

    def get_thread_status(self) -> dict[str, bool]:
        """Get status of all managed threads."""
        return {
            "data_acquisition": self.is_data_thread_alive(),
            "calibration": self.is_calibration_thread_alive(),
            "connection": self.is_connection_thread_alive(),
            # Note: sensor_reading thread removed (obsolete flow sensors)
        }
