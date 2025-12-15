from __future__ import annotations

"""Recording Manager - Handles data recording and export.

This class manages:
- Starting/stopping recording sessions
- Data logging to CSV/Excel formats
- Experiment metadata tracking
- File management and auto-save
- Event logging (injections, valve switches, etc.)

All file operations are handled safely to avoid blocking the UI.
"""

import builtins
import contextlib
import csv
import datetime as dt
import time
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from affilabs.utils.logger import logger


class RecordingManager(QObject):
    """Manages data recording and export."""

    # Signals for recording state
    recording_started = Signal(str)  # filename
    recording_stopped = Signal()
    recording_error = Signal(str)  # Error message
    event_logged = Signal(str)  # Event description

    def __init__(self, data_mgr) -> None:
        super().__init__()

        # Reference to data acquisition manager
        self.data_mgr = data_mgr

        # Recording state
        self.is_recording = False
        self.recording_start_time = None
        self.current_file = None
        self.csv_writer = None
        self.file_handle = None

        # Event log
        self.events = []  # List of (timestamp, event_description)

        # Recording settings
        self.output_directory = Path.home() / "Documents" / "ezControl Data"
        self.auto_save_interval = 60  # seconds
        self.last_save_time = 0

        # Initialized silently

    def start_recording(self, filename: str | None = None) -> None:
        """Start recording data to file."""
        if self.is_recording:
            logger.warning("Recording already in progress")
            return

        try:
            # Generate filename if not provided
            if filename is None:
                timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"AffiLabs_data_{timestamp}.csv"

            # Ensure output directory exists
            self.output_directory.mkdir(parents=True, exist_ok=True)

            # Create file path
            filepath = self.output_directory / filename

            # Open file for writing
            self.file_handle = open(filepath, "w", newline="", encoding="utf-8")
            self.csv_writer = csv.writer(self.file_handle)

            # Write header
            header = [
                "Timestamp",
                "Time_Elapsed",
                "Channel_A",
                "Channel_B",
                "Channel_C",
                "Channel_D",
            ]
            self.csv_writer.writerow(header)

            # Update state
            self.is_recording = True
            self.recording_start_time = time.time()
            self.current_file = filepath
            self.last_save_time = time.time()

            logger.info(f"Recording started: {filepath}")
            self.recording_started.emit(str(filepath))

        except Exception as e:
            logger.exception(f"Failed to start recording: {e}")
            self.recording_error.emit(f"Failed to start recording: {e}")
            self._cleanup_recording()

    def stop_recording(self) -> None:
        """Stop recording and close file."""
        if not self.is_recording:
            return

        try:
            # Write event log as footer
            if self.events:
                self.csv_writer.writerow([])
                self.csv_writer.writerow(["Event Log"])
                self.csv_writer.writerow(["Timestamp", "Event"])
                for timestamp, event in self.events:
                    elapsed = timestamp - self.recording_start_time
                    self.csv_writer.writerow([elapsed, event])

            # Close file
            self._cleanup_recording()

            logger.info("Recording stopped")
            self.recording_stopped.emit()

        except Exception as e:
            logger.exception(f"Error stopping recording: {e}")
            self.recording_error.emit(f"Error stopping recording: {e}")
            self._cleanup_recording()

    def _cleanup_recording(self) -> None:
        """Clean up recording resources."""
        if self.file_handle:
            with contextlib.suppress(builtins.BaseException):
                self.file_handle.close()
            self.file_handle = None

        self.csv_writer = None
        self.is_recording = False
        self.current_file = None
        self.events.clear()

    def record_data_point(self, data: dict) -> None:
        """Record a single data point to file.

        Args:
            data: Dictionary with keys 'channel_a', 'channel_b', 'channel_c', 'channel_d'
                  Each value should be a wavelength (float)

        """
        if not self.is_recording:
            return

        try:
            timestamp = time.time()
            elapsed = timestamp - self.recording_start_time

            # Write row: timestamp, elapsed, ch_a, ch_b, ch_c, ch_d
            row = [
                timestamp,
                elapsed,
                data.get("channel_a", ""),
                data.get("channel_b", ""),
                data.get("channel_c", ""),
                data.get("channel_d", ""),
            ]

            self.csv_writer.writerow(row)

            # Auto-save periodically
            current_time = time.time()
            if current_time - self.last_save_time > self.auto_save_interval:
                self.file_handle.flush()
                self.last_save_time = current_time

        except Exception as e:
            logger.error(f"Failed to record data point: {e}")

    def log_event(
        self,
        event: str,
        channel: str | None = None,
        flow: str | None = None,
        temp: str | None = None,
    ) -> None:
        """Log an event with timestamp.

        Args:
            event: Event description (e.g., "Injection started")
            channel: Optional channel identifier
            flow: Optional flow rate
            temp: Optional temperature

        """
        try:
            timestamp = time.time()

            # Build event string
            event_parts = [event]
            if channel:
                event_parts.append(f"Channel={channel}")
            if flow:
                event_parts.append(f"Flow={flow}")
            if temp:
                event_parts.append(f"Temp={temp}")

            event_str = " | ".join(event_parts)

            # Add to event log
            self.events.append((timestamp, event_str))

            logger.info(f"Event logged: {event_str}")
            self.event_logged.emit(event_str)

        except Exception as e:
            logger.error(f"Failed to log event: {e}")

    def export_to_excel(self, csv_path: Path, excel_path: Path | None = None) -> None:
        """Export CSV data to Excel format.

        Args:
            csv_path: Path to CSV file
            excel_path: Optional output path for Excel file

        """
        try:
            import pandas as pd

            if excel_path is None:
                excel_path = csv_path.with_suffix(".xlsx")

            # Read CSV
            df = pd.read_csv(csv_path)

            # Write to Excel
            df.to_excel(excel_path, index=False, engine="openpyxl")

            logger.info(f"Data exported to Excel: {excel_path}")

        except Exception as e:
            logger.exception(f"Failed to export to Excel: {e}")
            self.recording_error.emit(f"Failed to export to Excel: {e}")

    def set_output_directory(self, directory: Path) -> None:
        """Set the output directory for recordings."""
        try:
            directory = Path(directory)
            directory.mkdir(parents=True, exist_ok=True)
            self.output_directory = directory
            logger.info(f"Output directory set to: {directory}")
        except Exception as e:
            logger.error(f"Failed to set output directory: {e}")
            self.recording_error.emit(f"Invalid output directory: {e}")

    def get_recording_info(self) -> dict:
        """Get current recording information."""
        if not self.is_recording:
            return {
                "recording": False,
                "filename": None,
                "elapsed_time": 0,
                "event_count": 0,
            }

        elapsed = time.time() - self.recording_start_time if self.recording_start_time else 0

        return {
            "recording": True,
            "filename": str(self.current_file) if self.current_file else None,
            "elapsed_time": elapsed,
            "event_count": len(self.events),
        }
