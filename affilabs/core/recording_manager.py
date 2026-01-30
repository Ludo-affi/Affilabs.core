from __future__ import annotations

"""Recording Manager - Handles data recording and export.

This class manages:
- Starting/stopping recording sessions
- Data logging to Excel format with comprehensive metadata
- Experiment metadata tracking
- File management and auto-save
- Event logging (injections, valve switches, etc.)
- Cycle tracking and flag markers

All file operations are handled safely to avoid blocking the UI.
"""

import time
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from affilabs.services.data_collector import DataCollector
from affilabs.services.excel_exporter import ExcelExporter
from affilabs.utils.logger import logger


class RecordingManager(QObject):
    """Manages data recording and export to Excel with comprehensive metadata."""

    # Signals for recording state
    recording_started = Signal(str)  # filename
    recording_stopped = Signal()
    recording_error = Signal(str)  # Error message
    event_logged = Signal(str, float)  # Event description, timestamp

    def __init__(self, data_mgr, buffer_mgr=None) -> None:
        super().__init__()

        # Reference to data acquisition manager
        self.data_mgr = data_mgr

        # Reference to buffer manager (for Channels XY export)
        self.buffer_mgr = buffer_mgr

        # Delegate services (Separation of Concerns)
        self.data_collector = DataCollector()  # Handles in-memory data accumulation
        self.excel_exporter = ExcelExporter()  # Handles Excel file I/O

        # Recording state
        self.is_recording = False
        self.current_file = None
        self.recording_start_offset = 0.0  # Elapsed time when recording started (for t=0 export)

        # Recording settings
        self.output_directory = Path.home() / "Documents" / "Affilabs Data"
        self.auto_save_interval = 60  # seconds
        self.last_save_time = 0

        # Initialized silently

    def start_recording(self, filename: str | None = None, time_offset: float = 0.0) -> None:
        """Start recording data to file (if filename provided) or memory only.

        Args:
            filename: Full path to file for saving. If provided, creates file immediately.
                     If None, records to memory only until export.
            time_offset: Elapsed time when recording started (for t=0 export)
        """
        if self.is_recording:
            logger.warning("Recording already in progress")
            return

        try:
            # Update state
            self.is_recording = True
            self.current_file = filename  # Store filename if provided
            self.recording_start_offset = time_offset  # Store offset for t=0 export
            self.last_save_time = time.time()

            # Start data collection
            self.data_collector.start_collection(start_time=time.time())

            if filename:
                # Create file immediately for live recording
                from pathlib import Path

                filepath = Path(filename)
                filepath.parent.mkdir(parents=True, exist_ok=True)

                logger.info(f"Recording started - saving to file: {filename}")
                self.recording_started.emit(filename)
            else:
                logger.info("Recording started (data collecting to memory - will save on Export)")
                self.recording_started.emit("memory")

        except Exception as e:
            logger.exception(f"Failed to start recording: {e}")
            self.recording_error.emit(f"Failed to start recording: {e}")
            self._cleanup_recording()

    def stop_recording(self) -> None:
        """Stop recording and perform final save if recording to file."""
        if not self.is_recording:
            return

        try:
            # Final save if recording to file
            if self.current_file:
                self._save_to_file()
                logger.info(f"Recording stopped - final save to: {self.current_file}")
            else:
                logger.info("Recording stopped (data in memory - click Export to save)")

            # Stop recording
            self.is_recording = False
            self.current_file = None
            self.recording_stopped.emit()

        except Exception as e:
            logger.exception(f"Error stopping recording: {e}")
            self.recording_error.emit(f"Error stopping recording: {e}")
            self._cleanup_recording()

    def _save_to_file(self) -> None:
        """Save collected data to the current file."""
        if not self.current_file:
            return

        try:
            import pandas as pd
            from pathlib import Path

            # Get raw data from collector
            raw_data = self.data_collector.raw_data_rows
            if not raw_data:
                logger.warning("No data to save")
                return

            # Create DataFrame
            df_raw = pd.DataFrame(raw_data)

            # Sort by time then channel for consistent output
            if "time" in df_raw.columns and "channel" in df_raw.columns:
                df_raw = df_raw.sort_values(["time", "channel"])

            # Determine file format from extension
            filepath = Path(self.current_file)

            if filepath.suffix == ".xlsx":
                # Create Excel with multiple sheets
                with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
                    # Raw data sheet
                    df_raw.to_excel(writer, sheet_name="Raw Data", index=False)

                    # Cycles sheet if available
                    if self.data_collector.cycles:
                        df_cycles = pd.DataFrame(self.data_collector.cycles)
                        df_cycles.to_excel(writer, sheet_name="Cycles", index=False)

                    # Events sheet if available
                    if self.data_collector.events:
                        df_events = pd.DataFrame(self.data_collector.events)
                        df_events.to_excel(writer, sheet_name="Events", index=False)

                    # Metadata sheet
                    if self.data_collector.metadata:
                        df_meta = pd.DataFrame([self.data_collector.metadata])
                        df_meta.to_excel(writer, sheet_name="Metadata", index=False)

                    # Channels XY sheet (wide format: Time_A, SPR_A, Time_B, SPR_B, etc.)
                    # This matches the Export button format for consistency
                    if self.buffer_mgr is not None:
                        try:
                            import numpy as np

                            channels = ["a", "b", "c", "d"]
                            max_len = 0

                            # Find max length across all channels
                            for ch in channels:
                                if hasattr(self.buffer_mgr.cycle_data[ch], "time"):
                                    max_len = max(max_len, len(self.buffer_mgr.cycle_data[ch].time))

                            if max_len > 0:
                                sheet_data = {}
                                for ch in channels:
                                    ch_upper = ch.upper()

                                    # Get time and SPR data for this channel
                                    if hasattr(self.buffer_mgr.cycle_data[ch], "time"):
                                        ch_time = np.array(self.buffer_mgr.cycle_data[ch].time)
                                        ch_spr = np.array(self.buffer_mgr.cycle_data[ch].spr)

                                        # Pad to max length if needed
                                        if len(ch_time) < max_len:
                                            ch_time = np.pad(
                                                ch_time,
                                                (0, max_len - len(ch_time)),
                                                constant_values=np.nan,
                                            )
                                        if len(ch_spr) < max_len:
                                            ch_spr = np.pad(
                                                ch_spr,
                                                (0, max_len - len(ch_spr)),
                                                constant_values=np.nan,
                                            )
                                    else:
                                        # Channel has no data - fill with NaN
                                        ch_time = np.full((max_len,), np.nan)
                                        ch_spr = np.full((max_len,), np.nan)

                                    sheet_data[f"Time_{ch_upper}"] = ch_time
                                    sheet_data[f"SPR_{ch_upper}"] = ch_spr

                                df_xy = pd.DataFrame(sheet_data)
                                df_xy.to_excel(writer, sheet_name="Channels XY", index=False)
                                logger.debug(f"Created Channels XY sheet with {max_len} rows")
                        except Exception as e:
                            logger.warning(f"Could not create Channels XY sheet: {e}")

            elif filepath.suffix == ".csv":
                # CSV only saves raw data
                df_raw.to_csv(filepath, index=False)

            elif filepath.suffix == ".json":
                # JSON saves everything
                data_export = {
                    "raw_data": raw_data,
                    "cycles": self.data_collector.cycles,
                    "events": self.data_collector.events,
                    "metadata": self.data_collector.metadata,
                }
                import json

                with open(filepath, "w") as f:
                    json.dump(data_export, f, indent=2)

            logger.info(f"Data saved to {filepath} ({len(raw_data)} rows)")

        except Exception as e:
            logger.exception(f"Failed to save to file: {e}")
            self.recording_error.emit(f"Failed to save: {e}")

    def _cleanup_recording(self) -> None:
        """Clean up recording resources."""
        self.is_recording = False
        self.current_file = None
        self.data_collector.clear_all()

    def record_data_point(self, data: dict) -> None:
        """Record a single channel measurement to memory for later Excel export.

        Args:
            data: Dictionary with keys 'time', 'channel', 'value'
                  Example: {'time': 0.123, 'channel': 'a', 'value': 680.5}

        """
        if not self.is_recording:
            return

        try:
            # Store simple measurement row
            row_data = {
                "time": data.get("time", None),
                "channel": data.get("channel", ""),
                "value": data.get("value", None),
            }

            self.data_collector.add_data_point(row_data)

            # Auto-save to file if filename was provided (live recording mode)
            if self.current_file:
                current_time = time.time()
                if current_time - self.last_save_time >= self.auto_save_interval:
                    self._save_to_file()
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

            # Log to data collector
            self.data_collector.add_event(event_str, timestamp)

            logger.info(f"Event logged: {event_str}")
            self.event_logged.emit(event_str, timestamp)

        except Exception as e:
            logger.error(f"Failed to log event: {e}")

    def export_to_excel(self, csv_path: Path, excel_path: Path | None = None) -> None:
        """Export CSV data to Excel format (legacy method for compatibility).

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

    def add_cycle(self, cycle_data: dict) -> None:
        """Add cycle information to recording.

        Args:
            cycle_data: Dictionary with cycle information (type, start_time, end_time, etc.)
        """
        if not self.is_recording:
            return

        try:
            # Add to data collector
            self.data_collector.add_cycle(cycle_data)
        except Exception as e:
            logger.error(f"Failed to add cycle to recording: {e}")

    def add_flag(self, flag_data: dict) -> None:
        """Add flag marker to recording.

        Args:
            flag_data: Dictionary with flag information (type, channel, time, spr, timestamp, etc.)
        """
        if not self.is_recording:
            return

        try:
            # Add to data collector
            self.data_collector.add_flag(flag_data)
        except Exception as e:
            logger.error(f"Failed to add flag to recording: {e}")

    def update_metadata(self, key: str, value: any) -> None:
        """Update metadata for recording.

        Args:
            key: Metadata key
            value: Metadata value
        """
        if not self.is_recording:
            return

        try:
            self.data_collector.update_metadata(key, value)
        except Exception as e:
            logger.error(f"Failed to update metadata: {e}")

    def add_analysis_result(self, result_data: dict) -> None:
        """Add analysis measurement result to recording.

        Args:
            result_data: Dictionary with analysis results (segment, channel, assoc_shift, dissoc_shift, etc.)
        """
        if not self.is_recording:
            return

        try:
            # Add to data collector
            self.data_collector.add_analysis_result(result_data)
        except Exception as e:
            logger.error(f"Failed to add analysis result: {e}")

    def load_from_excel(self, filepath: Path) -> dict:
        """Load recorded data from Excel file.

        Args:
            filepath: Path to Excel file

        Returns:
            Dictionary with all loaded data sheets
        """
        return self.excel_exporter.load_from_excel(filepath)

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

        summary = self.data_collector.get_summary()

        return {
            "recording": True,
            "filename": str(self.current_file) if self.current_file else None,
            "elapsed_time": self.data_collector.get_elapsed_time(),
            "event_count": summary["events"],
        }
