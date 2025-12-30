"""SegmentManager - Manages EditableSegment instances for post-processing.

ARCHITECTURE LAYER: Manager (Business Logic)

This manager handles creation and management of EditableSegment instances
in the Edits tab. It coordinates segment creation, editing, and export.

RESPONSIBILITIES:
- Create segments from selected cycles
- Manage segment list
- Apply transformations
- Export segments to various formats

USAGE:
    segment_mgr = SegmentManager(app)

    # Create segment from cycle selection
    segment = segment_mgr.create_segment_from_cycles(
        cycle_nums=[1, 3],
        channel_sources={'a': 1, 'b': 3},
        name="Conc. 1 Blended"
    )

    # Export segment
    segment_mgr.export_segment(segment, "output.csv", format="tracedrawer")
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from affilabs.domain.editable_segment import EditableSegment
from affilabs.utils.logger import logger

if TYPE_CHECKING:
    from main import Application


class SegmentManager:
    """Manages EditableSegment instances for post-processing analysis.

    This manager coordinates segment creation, editing, and export in the
    Edits tab workflow.
    """

    def __init__(self, app: Application):
        """Initialize the segment manager.

        Args:
            app: Reference to Application instance
        """
        self.app = app
        self._segments: list[EditableSegment] = []
        logger.debug("✓ SegmentManager initialized")

    def create_segment_from_cycles(
        self,
        cycle_nums: list[int],
        channel_sources: dict[str, int] | None = None,
        name: str = "",
        time_range: tuple[float, float] | None = None,
    ) -> EditableSegment:
        """Create new EditableSegment from selected cycles.

        Args:
            cycle_nums: List of cycle numbers to include
            channel_sources: Which cycle each channel comes from {'a': 1, 'b': 3}
                           If None, uses first cycle for all channels
            name: Segment name (auto-generated if empty)
            time_range: Optional custom time range, otherwise uses cycle boundaries

        Returns:
            Created EditableSegment instance
        """
        # Auto-generate name if not provided
        if not name:
            if len(cycle_nums) == 1:
                name = f"Segment {cycle_nums[0]}"
            else:
                name = f"Blended {'+'.join(map(str, cycle_nums))}"

        # Default channel sources to first cycle
        if channel_sources is None:
            first_cycle = cycle_nums[0]
            channel_sources = {ch: first_cycle for ch in ["a", "b", "c", "d"]}

        # Determine time range from cycles if not provided
        if time_range is None:
            # Get loaded cycles data
            if not hasattr(self.app.main_window, "_loaded_cycles_data"):
                logger.error("No loaded cycle data available")
                raise ValueError("No loaded cycle data available")

            cycles_data = self.app.main_window._loaded_cycles_data

            # Find min start and max end from selected cycles
            start_times = []
            end_times = []

            for cycle_num in cycle_nums:
                if cycle_num <= len(cycles_data):
                    cycle = cycles_data[cycle_num - 1]
                    start = cycle.get("start_time_sensorgram", cycle.get("sensorgram_time"))
                    end = cycle.get("end_time_sensorgram")

                    if start is not None:
                        start_times.append(start)
                    if end is not None:
                        end_times.append(end)

            if start_times and end_times:
                time_range = (min(start_times), max(end_times))
            else:
                time_range = (0.0, 0.0)

        # Create segment
        segment = EditableSegment(
            name=name,
            source_cycles=cycle_nums,
            time_range=time_range,
            channel_sources=channel_sources,
        )

        self._segments.append(segment)
        logger.info(f"✓ Created segment: {segment}")

        return segment

    def get_segments(self) -> list[EditableSegment]:
        """Get all created segments."""
        return self._segments.copy()

    def remove_segment(self, segment: EditableSegment) -> bool:
        """Remove segment from manager.

        Args:
            segment: Segment to remove

        Returns:
            True if removed, False if not found
        """
        try:
            self._segments.remove(segment)
            logger.info(f"✓ Removed segment: {segment.name}")
            return True
        except ValueError:
            logger.warning(f"Segment not found: {segment.name}")
            return False

    def export_segment(
        self, segment: EditableSegment, filepath: str | Path, format: str = "tracedrawer"
    ) -> bool:
        """Export segment to file.

        Args:
            segment: Segment to export
            filepath: Output file path
            format: Export format ('tracedrawer', 'excel', 'json')

        Returns:
            True if successful, False otherwise
        """
        try:
            filepath = Path(filepath)

            # Get raw data from recording manager
            if not hasattr(self.app, "recording_mgr"):
                logger.error("Recording manager not available")
                return False

            raw_data = self.app.recording_mgr.data_collector.raw_data_rows

            if not raw_data:
                logger.error("No raw data available to export")
                return False

            # Extract data for segment's time range
            time_data = []
            spr_data = {"a": [], "b": [], "c": [], "d": []}

            start_time, end_time = segment.time_range

            for row in raw_data:
                time = row.get("elapsed", row.get("time", 0))
                if start_time <= time <= end_time:
                    time_data.append(time)
                    for ch in ["a", "b", "c", "d"]:
                        wavelength = row.get(f"wavelength_{ch}")
                        spr_data[ch].append(wavelength if wavelength is not None else 0)

            if not time_data:
                logger.error(f"No data found in time range {start_time:.1f}-{end_time:.1f}s")
                return False

            # Convert to numpy arrays
            import numpy as np

            time_array = np.array(time_data)
            spr_arrays = {ch: np.array(data) for ch, data in spr_data.items()}

            # Export based on format
            if format == "tracedrawer":
                segment.export_to_tracedrawer_csv(str(filepath), time_array, spr_arrays)
                logger.info(f"✓ Exported segment to TraceDrawer CSV: {filepath}")

            elif format == "excel":
                # Use ExcelExporter for Excel format
                logger.warning("Excel export not yet implemented for segments")
                return False

            elif format == "json":
                # Export as JSON
                import json

                export_data = segment.to_export_dict()
                with open(filepath, "w") as f:
                    json.dump(export_data, f, indent=2)
                logger.info(f"✓ Exported segment to JSON: {filepath}")

            else:
                logger.error(f"Unknown export format: {format}")
                return False

            return True

        except Exception as e:
            logger.exception(f"Error exporting segment: {e}")
            return False

    def clear_segments(self):
        """Clear all segments."""
        self._segments.clear()
        logger.info("✓ All segments cleared")
