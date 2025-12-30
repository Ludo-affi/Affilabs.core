"""Excel Exporter - Handles Excel file generation and data export.

ARCHITECTURE LAYER: Service (Phase 3 - Application Services)

This class is responsible for:
- Converting in-memory data to Excel format
- Creating multi-sheet Excel workbooks
- File I/O operations (save/load)
- Data serialization/deserialization

SEPARATION OF CONCERNS:
- RecordingManager: Orchestrates recording lifecycle
- DataCollector: Accumulates data in memory
- ExcelExporter: Handles file I/O and Excel formatting

BENEFITS:
- Single Responsibility: Only handles Excel operations
- Testable: Can test Excel export without RecordingManager
- Reusable: Can export data from other sources
- Swappable: Easy to add CSV, JSON, or other export formats
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import TYPE_CHECKING

from affilabs.utils.logger import logger

if TYPE_CHECKING:
    pass


class ExcelExporter:
    """Handles Excel file generation and data import/export operations."""

    def __init__(self):
        """Initialize the Excel exporter."""
        pass

    def export_to_excel(
        self,
        filepath: Path,
        raw_data_rows: list[dict],
        cycles: list[dict],
        flags: list[dict],
        events: list[tuple],
        analysis_results: list[dict],
        metadata: dict,
        recording_start_time: float,
        alignment_data: dict | None = None,
    ) -> None:
        """Export all data to Excel file with multiple sheets.

        Args:
            filepath: Path to Excel file
            raw_data_rows: List of raw data point dicts
            cycles: List of cycle dicts
            flags: List of flag dicts
            events: List of (timestamp, event_description) tuples
            analysis_results: List of analysis measurement dicts
            metadata: Dictionary of metadata key-value pairs
            recording_start_time: Unix timestamp of recording start
            alignment_data: Dict mapping cycle_index -> {'channel': str, 'shift': float}

        Raises:
            ImportError: If pandas/openpyxl not installed
            IOError: If file cannot be written
        """
        try:
            import pandas as pd

            with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
                # Sheet 1: Raw Data
                if raw_data_rows:
                    df_raw = pd.DataFrame(raw_data_rows)
                    df_raw.to_excel(writer, sheet_name="Raw Data", index=False)
                    logger.debug(f"Exported {len(raw_data_rows)} raw data points")

                # Sheet 2: Cycles
                if cycles:
                    df_cycles = pd.DataFrame(cycles)
                    df_cycles.to_excel(writer, sheet_name="Cycles", index=False)
                    logger.debug(f"Exported {len(cycles)} cycles")

                # Sheet 3: Flags
                if flags:
                    df_flags = pd.DataFrame(flags)
                    df_flags.to_excel(writer, sheet_name="Flags", index=False)
                    logger.debug(f"Exported {len(flags)} flags")

                # Sheet 4: Events
                if events:
                    events_data = []
                    for timestamp, event in events:
                        elapsed = timestamp - recording_start_time
                        formatted_time = dt.datetime.fromtimestamp(timestamp).strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                        events_data.append(
                            {
                                "elapsed": elapsed,
                                "timestamp": formatted_time,
                                "event": event,
                            }
                        )
                    df_events = pd.DataFrame(events_data)
                    df_events.to_excel(writer, sheet_name="Events", index=False)
                    logger.debug(f"Exported {len(events)} events")

                # Sheet 5: Analysis Results
                if analysis_results:
                    df_analysis = pd.DataFrame(analysis_results)
                    df_analysis.to_excel(writer, sheet_name="Analysis", index=False)
                    logger.debug(f"Exported {len(analysis_results)} analysis results")

                # Sheet 6: Metadata
                if metadata:
                    # Convert metadata dict to DataFrame
                    metadata_items = [{"key": k, "value": str(v)} for k, v in metadata.items()]
                    df_meta = pd.DataFrame(metadata_items)
                    df_meta.to_excel(writer, sheet_name="Metadata", index=False)
                    logger.debug(f"Exported {len(metadata)} metadata items")

                # Sheet 7: Alignment (Edits tab settings)
                if alignment_data:
                    alignment_rows = []
                    for cycle_idx, settings in alignment_data.items():
                        alignment_rows.append(
                            {
                                "Cycle_Index": cycle_idx,
                                "Channel_Filter": settings.get("channel", "All"),
                                "Time_Shift_s": settings.get("shift", 0.0),
                            }
                        )
                    df_alignment = pd.DataFrame(alignment_rows)
                    df_alignment.to_excel(writer, sheet_name="Alignment", index=False)
                    logger.debug(f"Exported alignment settings for {len(alignment_rows)} cycles")

            logger.info(f"✓ Exported to Excel: {filepath}")

        except ImportError:
            logger.error(
                "pandas or openpyxl not installed. Install with: pip install pandas openpyxl"
            )
            raise

        except Exception as e:
            logger.error(f"Failed to export to Excel: {e}")
            raise

    def load_from_excel(self, filepath: Path) -> dict | None:
        """Load recorded data from Excel file.

        Args:
            filepath: Path to Excel file

        Returns:
            Dictionary with keys:
                - raw_data: List of data point dicts
                - cycles: List of cycle dicts
                - flags: List of flag dicts
                - events: List of event dicts
                - analysis: List of analysis result dicts
                - metadata: Dictionary of metadata

        Returns None if load fails.
        """
        try:
            import pandas as pd

            # Read all sheets
            excel_data = pd.read_excel(filepath, sheet_name=None, engine="openpyxl")

            loaded_data = {
                "raw_data": (
                    excel_data.get("Raw Data", pd.DataFrame()).to_dict("records")
                    if "Raw Data" in excel_data
                    else []
                ),
                "cycles": (
                    excel_data.get("Cycles", pd.DataFrame()).to_dict("records")
                    if "Cycles" in excel_data
                    else []
                ),
                "flags": (
                    excel_data.get("Flags", pd.DataFrame()).to_dict("records")
                    if "Flags" in excel_data
                    else []
                ),
                "events": (
                    excel_data.get("Events", pd.DataFrame()).to_dict("records")
                    if "Events" in excel_data
                    else []
                ),
                "analysis": (
                    excel_data.get("Analysis", pd.DataFrame()).to_dict("records")
                    if "Analysis" in excel_data
                    else []
                ),
                "alignment": (
                    excel_data.get("Alignment", pd.DataFrame()).to_dict("records")
                    if "Alignment" in excel_data
                    else []
                ),
                "metadata": {},
            }

            # Convert metadata from list format to dict
            if "Metadata" in excel_data:
                meta_df = excel_data["Metadata"]
                if not meta_df.empty:
                    # Check if required columns exist
                    if "key" not in meta_df.columns or "value" not in meta_df.columns:
                        logger.warning(
                            f"Metadata sheet missing 'key' or 'value' column. Found: {list(meta_df.columns)}"
                        )
                    else:
                        for _, row in meta_df.iterrows():
                            loaded_data["metadata"][row["key"]] = row["value"]

            logger.info(f"✓ Loaded data from Excel: {filepath}")
            logger.info(f"  - Raw data points: {len(loaded_data['raw_data'])}")
            logger.info(f"  - Cycles: {len(loaded_data['cycles'])}")
            logger.info(f"  - Flags: {len(loaded_data['flags'])}")
            logger.info(f"  - Events: {len(loaded_data['events'])}")
            logger.info(f"  - Analysis results: {len(loaded_data['analysis'])}")

            return loaded_data

        except ImportError:
            logger.error(
                "pandas or openpyxl not installed. Install with: pip install pandas openpyxl"
            )
            return None

        except Exception as e:
            logger.error(f"Failed to load Excel file: {e}")
            return None

    def validate_excel_file(self, filepath: Path) -> bool:
        """Check if file exists and is a valid Excel file.

        Args:
            filepath: Path to Excel file

        Returns:
            True if file is valid Excel, False otherwise
        """
        if not filepath.exists():
            logger.warning(f"File does not exist: {filepath}")
            return False

        if filepath.suffix not in [".xlsx", ".xls"]:
            logger.warning(f"File is not Excel format (.xlsx/.xls): {filepath}")
            return False

        try:
            import pandas as pd

            # Try to read file
            pd.read_excel(filepath, engine="openpyxl", nrows=0)
            return True

        except Exception as e:
            logger.warning(f"File is not valid Excel: {e}")
            return False
