from __future__ import annotations

"""Recording Manager - Handles data recording and export.

This class manages:
- Starting/stopping recording sessions
- Data logging to Excel format with comprehensive metadata
- Experiment metadata tracking
- File management and auto-save
- Event logging (injections, valve switches, etc.)
- Cycle tracking and flag markers
- Unified timeline event stream (all events in one place)

All file operations are handled safely to avoid blocking the UI.
"""

import time
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from affilabs.domain.timeline import TimelineContext, TimelineEventStream
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

    def __init__(self, data_mgr, buffer_mgr=None, user_manager=None) -> None:
        super().__init__()

        # Reference to data acquisition manager
        self.data_mgr = data_mgr

        # Reference to buffer manager (for Channels XY export)
        self.buffer_mgr = buffer_mgr

        # User profile manager (for experiment count tracking)
        self.user_manager = user_manager

        # Delegate services (Separation of Concerns)
        self.data_collector = DataCollector()  # Handles in-memory data accumulation
        self.excel_exporter = ExcelExporter()  # Handles Excel file I/O

        # Timeline state (unified event system)
        self._timeline_context: TimelineContext | None = None
        self._timeline_stream = TimelineEventStream()  # Unified event repository

        # Recording state
        self.is_recording = False
        self.current_file = None
        self.recording_start_offset = 0.0  # Elapsed time when recording started (for t=0 export)

        # Recording settings
        # Default output directory — updated to user-specific path by _get_user_output_directory()
        self.output_directory = Path.home() / "Documents" / "Affilabs Data"
        self.auto_save_interval = 60  # seconds
        self.last_save_time = 0

    def get_user_output_directory(self) -> Path:
        """Get user-specific output directory: Documents/Affilabs Data/<username>/SPR_data/.

        Always resolves the current user dynamically (same logic as Edits tab).
        Falls back to generic Affilabs Data if no user is set.

        Returns:
            Path to user-specific export directory
        """
        username = ""
        if self.user_manager:
            username = self.user_manager.get_current_user() or ""
        if username:
            user_dir = Path.home() / "Documents" / "Affilabs Data" / username / "SPR_data"
        else:
            user_dir = self.output_directory
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir

    def get_timeline_context(self) -> TimelineContext | None:
        """Get the current recording's timeline context.

        Returns:
            TimelineContext if recording, None otherwise.
            Use this to convert times or check if recording is active.
        """
        return self._timeline_context

    def get_timeline_stream(self) -> TimelineEventStream:
        """Get the unified event stream (all timeline events in one place).

        Returns:
            TimelineEventStream for adding/querying events.
            Managers and presenters query this stream for:
            - Injection flags
            - Wash/regeneration events
            - Cycle boundaries
            - Auto-markers and user annotations
        """
        return self._timeline_stream

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

            # Create timeline context for this recording session
            self._timeline_context = TimelineContext(
                recording_start_time=time.time(),
                recording_start_offset=time_offset
            )
            # Reset timeline stream for new recording
            self._timeline_stream = TimelineEventStream()
            logger.info(f"Timeline context initialized (offset={time_offset}s)")

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

                # Increment experiment count for current user
                try:
                    if self.user_manager:
                        new_count = self.user_manager.increment_experiment_count()
                        logger.info(f"Experiment count incremented: {new_count}")
                except Exception as e:
                    logger.warning(f"Could not increment experiment count: {e}")
            else:
                logger.info("Recording stopped (data in memory - click Export to save)")

            # Stop recording
            self.is_recording = False
            self.current_file = None
            self._timeline_context = None  # Clear timeline context
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
                # Use dedicated Excel exporter service for consistency across all export paths
                # Build Channels XY sheet for export
                try:
                    from affilabs.utils.export_helpers import ExportHelpers
                    df_xy = ExportHelpers.build_channels_xy_dataframe(
                        self.buffer_mgr,
                        channels=["a", "b", "c", "d"]
                    ) if self.buffer_mgr else None
                except Exception as e:
                    logger.warning(f"Could not build Channels XY sheet: {e}")
                    df_xy = None
                
                self.excel_exporter.export_to_excel(
                    filepath=filepath,
                    raw_data_rows=self.data_collector.raw_data_rows,
                    cycles=self.data_collector.cycles,
                    flags=self.data_collector.flags,
                    events=self.data_collector.events,
                    analysis_results=[],  # Not used in recording flow
                    metadata=self.data_collector.metadata,
                    recording_start_time=self.data_collector.recording_start_time,
                    alignment_data=None,  # Not used in recording flow
                    channels_xy_dataframe=df_xy,
                    timeline_stream=self.get_timeline_stream(),
                )

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
        self._timeline_context = None
        self._timeline_stream = TimelineEventStream()
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
