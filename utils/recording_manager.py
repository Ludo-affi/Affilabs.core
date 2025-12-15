"""Recording Manager Module

Handles recording operations, data saving coordination, and export functionality
for SPR experiments.

Author: Extracted from main.py during Phase 10 refactoring
Date: October 8, 2025
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import QFileDialog

from affilabs.widgets.message import show_message
from settings.settings import RECORDING_INTERVAL, TIME_ZONE
from utils.data_io_manager import DataIOManager
from utils.logger import logger

if TYPE_CHECKING:
    from PySide6.QtCore import QTimer

    from affilabs.affilabs_core_ui import AffilabsMainWindow as MainWindow


class RecordingManager:
    """Manages recording operations and data saving coordination.

    Handles:
    - Recording start/stop with directory selection
    - Automatic data saving during recording
    - Manual data export operations
    - Recording state management
    """

    def __init__(
        self,
        main_window: MainWindow,
        rec_timer: QTimer,
        data_io: DataIOManager,
    ):
        """Initialize the Recording Manager.

        Args:
            main_window: Main window instance for UI interactions
            rec_timer: Timer for periodic recording saves
            data_io: Data I/O manager for file operations

        """
        self.main_window = main_window
        self.rec_timer = rec_timer
        self.data_io = data_io

        # Recording state - managed internally
        self.recording = False
        self.rec_dir = ""

    def start_recording(
        self,
        device_config: dict[str, str],
        parent_widget: Any = None,
    ) -> bool:
        """Start recording data to a user-selected directory.

        Args:
            device_config: Device configuration dictionary
            parent_widget: Parent widget for dialog (optional)

        Returns:
            bool: True if recording started successfully, False otherwise

        """
        try:
            # Get recording directory from user
            self.rec_dir = QFileDialog.getExistingDirectory(
                parent_widget,
                "Choose directory for recorded data files",
                "",
            )

            if self.rec_dir in {None, ""}:
                logger.debug(f"Recording directory could not be opened: {self.rec_dir}")
                return False

            # Create timestamped recording directory
            time_data = dt.datetime.now(TIME_ZONE)
            self.rec_dir = (
                f"{self.rec_dir}/Recording {time_data.hour:02d}{time_data.minute:02d}"
            )

            logger.debug(f"recording path: {self.rec_dir}")

            # Start recording on sensorgram widget if SPR controller available
            if device_config["ctrl"] != "":
                self.main_window.sensorgram.start_recording(self.rec_dir)

            # Set recording state
            self.recording = True
            self.main_window.set_recording(self.recording)

            # Start periodic saving
            self.rec_timer.start(1000 * RECORDING_INTERVAL)

            logger.info(f"Recording started: {self.rec_dir}")
            return True

        except Exception as e:
            logger.exception(f"Error while starting recording: {e}")
            return False

    def stop_recording(self) -> None:
        """Stop recording and update UI state."""
        self.recording = False
        self.rec_timer.stop()
        self.main_window.set_recording(self.recording)
        logger.info("Recording stopped")

    def toggle_recording(
        self,
        device_config: dict[str, str],
        set_start_callback: Callable[[], None],
        clear_buffers_callback: Callable[[], None],
        parent_widget: Any = None,
    ) -> Optional[bool]:
        """Toggle recording state - start if stopped, stop if recording.

        Args:
            device_config: Device configuration dictionary
            set_start_callback: Callback to set start state
            clear_buffers_callback: Callback to clear sensor buffers
            parent_widget: Parent widget for dialogs (optional)

        Returns:
            Optional[bool]: Recording state or None if no change

        """
        if not self.recording:
            # Start recording
            success = self.start_recording(device_config, parent_widget)
            if success:
                # Execute callbacks for recording setup
                set_start_callback()
                clear_buffers_callback()
                return True
            return False
        # Stop recording
        self.stop_recording()
        return None

    def save_recorded_data(
        self,
        device_config: dict[str, str],
        temp_log: dict[str, list],
        log_ch1: dict[str, Any],
        log_ch2: dict[str, Any],
        knx: Optional[Any] = None,
    ) -> None:
        """Save all recorded data during recording session.

        Args:
            device_config: Device configuration dictionary
            temp_log: Temperature log data
            log_ch1: Channel A kinetic log data
            log_ch2: Channel B kinetic log data
            knx: KNX device instance (optional)

        """
        try:
            # Save SPR sensorgram data
            if device_config["ctrl"] != "":
                logger.debug("saving SPR data")
                self.main_window.sensorgram.save_data(self.rec_dir)

                # Save temperature log for P4SPR devices
                if device_config["ctrl"] == "PicoP4SPR":
                    self._save_temperature_log(temp_log)

            # Save kinetic logs for KNX devices
            if device_config["knx"] != "" or device_config["ctrl"] in [
                "PicoEZSPR",
            ]:
                logger.debug("saving kinetic log")
                self._save_kinetic_logs(log_ch1, log_ch2, device_config, knx)

            # Restart timer for next save cycle
            self.rec_timer.start()

        except Exception as e:
            logger.exception(f"Error saving recorded data: {e}")

    def manual_export_data(self, parent_widget: Any = None) -> bool:
        """Manually export current data to user-selected directory.

        Args:
            parent_widget: Parent widget for dialog (optional)

        Returns:
            bool: True if export successful, False otherwise

        """
        try:
            save_dir = QFileDialog.getExistingDirectory(
                parent_widget,
                "Choose directory for recorded data files",
                "",
            )

            if save_dir in [None, ""]:
                logger.debug(f"Directory could not be opened: {save_dir}")
                return False

            # Export data to selected directory
            self.main_window.sensorgram.save_data(f"{save_dir}/Export")

            # Show success message
            show_message(
                msg="Files exported successfully!",
                msg_type="Information",
                auto_close_time=3,
            )

            logger.info(f"Manual export completed: {save_dir}/Export")
            return True

        except Exception as e:
            logger.exception(f"Error during manual export: {e}")
            return False

    def _save_temperature_log(self, temp_log: dict[str, list]) -> None:
        """Save temperature log using DataIOManager."""
        try:
            self.data_io.save_temperature_log(self.rec_dir, temp_log)
        except Exception as e:
            logger.exception(f"Error while saving temperature log data: {e}")

    def _save_kinetic_logs(
        self,
        log_ch1: dict[str, Any],
        log_ch2: dict[str, Any],
        device_config: dict[str, str],
        knx: Optional[Any] = None,
    ) -> None:
        """Save kinetic logs using DataIOManager."""
        if knx is not None:
            try:
                knx_version = knx.version if hasattr(knx, "version") else "1.0"

                # Save Channel A log
                self.data_io.save_kinetic_log(self.rec_dir, log_ch1, "A", knx_version)

                # Save Channel B log for dual-channel devices
                if device_config["ctrl"] in ["PicoEZSPR"] or device_config["knx"] in [
                    "KNX2",
                ]:  # PicoKNX2 disabled (obsolete)
                    self.data_io.save_kinetic_log(
                        self.rec_dir,
                        log_ch2,
                        "B",
                        knx_version,
                    )

            except Exception as e:
                logger.exception(f"Error while saving kinetic log data: {e}")

    def get_recording_state(self) -> dict[str, Any]:
        """Get current recording state information.

        Returns:
            dict: Recording state with directory and status

        """
        return {
            "recording": self.recording,
            "rec_dir": self.rec_dir,
            "timer_active": self.rec_timer.isActive() if self.rec_timer else False,
        }

    def cleanup(self) -> None:
        """Clean up recording manager resources."""
        if self.recording:
            self.stop_recording()
        logger.debug("RecordingManager cleanup completed")
