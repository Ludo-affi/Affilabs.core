"""Data Collector - In-memory data accumulation for recordings.

ARCHITECTURE LAYER: Service (Phase 3 - Application Services)

This class is responsible for:
- Accumulating data points in memory during recording
- Managing cycles, flags, events, and analysis results
- Providing data snapshots for export
- Clearing/resetting data collections

SEPARATION OF CONCERNS:
- RecordingManager: Orchestrates recording lifecycle
- DataCollector: Accumulates data in memory (this class)
- ExcelExporter: Handles file I/O and Excel formatting

BENEFITS:
- Single Responsibility: Only manages in-memory data
- Testable: Can test data accumulation without file I/O
- Thread-safe potential: Easy to add locking if needed
- Memory management: Centralized control of data growth
"""

from __future__ import annotations

import datetime as dt
import time
from typing import Any

from affilabs.utils.logger import logger


class DataCollector:
    """Manages in-memory data collection during recording sessions."""

    def __init__(self):
        """Initialize the data collector with empty collections."""

        # Data storage collections
        self.raw_data_rows: list[dict] = []  # Raw sensor data points
        self.events: list[tuple[float, str]] = []  # (timestamp, description)
        self.cycles: list[dict] = []  # Cycle information
        self.flags: list[dict] = []  # Flag markers
        self.metadata: dict[str, Any] = {}  # General metadata
        self.analysis_results: list[dict] = []  # Analysis measurements

        # Recording context
        self.recording_start_time: float | None = None

    def start_collection(self, start_time: float | None = None) -> None:
        """Start a new data collection session.

        Args:
            start_time: Unix timestamp for recording start (defaults to now)
        """
        self.recording_start_time = start_time or time.time()

        # Initialize metadata with recording start in human-readable format
        # Use standard datetime format that Excel and users can easily read
        self.metadata = {
            "recording_start": dt.datetime.fromtimestamp(self.recording_start_time).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "recording_start_iso": dt.datetime.fromtimestamp(self.recording_start_time).isoformat(),
        }

        logger.debug(f"Data collection started at {self.recording_start_time}")

    def clear_all(self) -> None:
        """Clear all collected data and reset to empty state."""
        self.raw_data_rows.clear()
        self.events.clear()
        self.cycles.clear()
        self.flags.clear()
        self.analysis_results.clear()
        self.metadata.clear()
        self.recording_start_time = None

        logger.debug("All data collections cleared")

    def add_data_point(self, data: dict) -> None:
        """Add a raw data point to collection.

        Args:
            data: Dictionary with data point fields (time, channels, etc.)
        """
        self.raw_data_rows.append(data)

    def add_event(self, event_description: str, timestamp: float | None = None) -> None:
        """Add an event to the event log.

        Args:
            event_description: Description of the event
            timestamp: Unix timestamp (defaults to now)
        """
        timestamp = timestamp or time.time()
        self.events.append((timestamp, event_description))
        logger.debug(f"Event logged: {event_description}")

    def add_cycle(self, cycle_data: dict) -> None:
        """Add cycle information to collection.

        Args:
            cycle_data: Dictionary with cycle information
                (type, start_time, end_time, duration, etc.)
        """
        self.cycles.append(cycle_data)
        logger.debug(
            f"Cycle added: {cycle_data.get('type', 'Unknown')} "
            f"(Cycle {cycle_data.get('cycle_num', '?')})"
        )

    def add_flag(self, flag_data: dict) -> None:
        """Add flag marker to collection.

        Args:
            flag_data: Dictionary with flag information
                (type, channel, time, spr, timestamp, etc.)
        """
        self.flags.append(flag_data)
        logger.debug(
            f"Flag added: {flag_data.get('type', 'Unknown')} "
            f"on Channel {flag_data.get('channel', '?')}"
        )

    def add_analysis_result(self, result_data: dict) -> None:
        """Add analysis measurement result to collection.

        Args:
            result_data: Dictionary with analysis results
                (segment, channel, assoc_shift, dissoc_shift, etc.)
        """
        self.analysis_results.append(result_data)
        logger.debug(f"Analysis result added: Segment {result_data.get('segment', 'Unknown')}")

    def update_metadata(self, key: str, value: Any) -> None:
        """Update or add metadata entry.

        Args:
            key: Metadata key
            value: Metadata value (will be converted to string for Excel)
        """
        self.metadata[key] = value
        logger.debug(f"Metadata updated: {key} = {value}")

    def get_summary(self) -> dict:
        """Get summary statistics of collected data.

        Returns:
            Dictionary with counts of each data type
        """
        return {
            "raw_data_points": len(self.raw_data_rows),
            "events": len(self.events),
            "cycles": len(self.cycles),
            "flags": len(self.flags),
            "analysis_results": len(self.analysis_results),
            "metadata_items": len(self.metadata),
            "recording_start": self.recording_start_time,
        }

    def get_all_data(self) -> dict:
        """Get all collected data for export.

        Returns:
            Dictionary containing all data collections
        """
        return {
            "raw_data_rows": self.raw_data_rows,
            "events": self.events,
            "cycles": self.cycles,
            "flags": self.flags,
            "analysis_results": self.analysis_results,
            "metadata": self.metadata,
            "recording_start_time": self.recording_start_time,
        }

    def get_data_count(self) -> int:
        """Get total number of raw data points collected.

        Returns:
            Number of raw data points
        """
        return len(self.raw_data_rows)

    def get_elapsed_time(self) -> float:
        """Get elapsed time since recording started.

        Returns:
            Elapsed time in seconds (0 if not started)
        """
        if self.recording_start_time is None:
            return 0.0
        return time.time() - self.recording_start_time

    def has_data(self) -> bool:
        """Check if any data has been collected.

        Returns:
            True if any data exists, False otherwise
        """
        return (
            len(self.raw_data_rows) > 0
            or len(self.events) > 0
            or len(self.cycles) > 0
            or len(self.flags) > 0
            or len(self.analysis_results) > 0
        )
