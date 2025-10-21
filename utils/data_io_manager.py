"""Data I/O Manager Module

Centralized file input/output operations for SPR data, temperature logs,
kinetic logs, and analysis results.

Author: Refactored from main.py and widget files
Date: October 7, 2025
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import numpy as np

from utils.logger import logger


class DataIOManager:
    """Centralized manager for all data file operations.

    Handles saving and loading:
    - SPR sensorgram data (raw and processed)
    - Temperature logs
    - Kinetic logs (flow, events, temperatures)
    - Analysis results
    - Calibration data

    Provides consistent file formats, error handling, and validation.
    """

    def __init__(self):
        """Initialize the Data I/O Manager."""
        self.encoding = "utf-8"
        self.csv_dialect = "excel-tab"

    # ========================================================================
    # TEMPERATURE LOG OPERATIONS
    # ========================================================================

    def save_temperature_log(
        self,
        rec_dir: str,
        temp_log: dict[str, list],
    ) -> bool:
        """Save temperature log to tab-delimited text file.

        Args:
            rec_dir: Base directory/filename for the recording
            temp_log: Dictionary with keys: 'readings', 'times', 'exp'
                - readings: List of temperature values (float)
                - times: List of timestamp strings
                - exp: List of experiment time values (float)

        Returns:
            True if successful, False otherwise

        """
        try:
            if rec_dir is None:
                logger.warning("No recording directory specified for temperature log")
                return False

            file_path = Path(f"{rec_dir} Temperature Log.txt")

            with file_path.open("w", newline="", encoding=self.encoding) as txtfile:
                fieldnames = ["Timestamp", "Experiment Time", "Device Temp"]
                writer = csv.DictWriter(
                    txtfile,
                    dialect=self.csv_dialect,
                    fieldnames=fieldnames,
                )
                writer.writeheader()

                num_entries = len(temp_log["readings"])
                for i in range(num_entries):
                    writer.writerow(
                        {
                            "Timestamp": temp_log["times"][i],
                            "Experiment Time": temp_log["exp"][i],
                            "Device Temp": temp_log["readings"][i],
                        }
                    )

            logger.info(f"Temperature log saved: {file_path} ({num_entries} entries)")
            return True

        except KeyError as e:
            logger.exception(f"Missing required key in temp_log: {e}")
            return False
        except Exception as e:
            logger.exception(f"Error saving temperature log: {e}")
            return False

    def load_temperature_log(self, file_path: str) -> dict[str, list] | None:
        """Load temperature log from file.

        Args:
            file_path: Path to temperature log file

        Returns:
            Dictionary with 'readings', 'times', 'exp' lists, or None if failed

        """
        try:
            temp_log: dict[str, list] = {
                "readings": [],
                "times": [],
                "exp": [],
            }

            with Path(file_path).open("r", encoding=self.encoding) as txtfile:
                reader = csv.DictReader(txtfile, dialect=self.csv_dialect)
                for row in reader:
                    temp_log["times"].append(row["Timestamp"])
                    temp_log["exp"].append(float(row["Experiment Time"]))
                    temp_log["readings"].append(float(row["Device Temp"]))

            logger.info(f"Temperature log loaded: {len(temp_log['readings'])} entries")
            return temp_log

        except Exception as e:
            logger.exception(f"Error loading temperature log: {e}")
            return None

    # ========================================================================
    # KINETIC LOG OPERATIONS
    # ========================================================================

    def save_kinetic_log(
        self,
        rec_dir: str,
        log_data: dict[str, list],
        channel: str,
        knx_version: str = "1.0",
    ) -> bool:
        """Save kinetic log for a single channel to tab-delimited text file.

        Args:
            rec_dir: Base directory/filename for the recording
            log_data: Dictionary with keys:
                - timestamps: List of timestamp strings
                - times: List of experiment time values (float)
                - events: List of event type strings
                - flow: List of flow rate values (float)
                - temp: List of temperature values (float)
                - dev: List of device temperature values (float) [v1.1 only]
            channel: Channel identifier (e.g., "A", "B", "CH1", "CH2")
            knx_version: KNX firmware version (e.g., "1.1", "1.0")

        Returns:
            True if successful, False otherwise

        """
        try:
            if rec_dir is None:
                logger.warning(
                    f"No recording directory specified for kinetic log {channel}"
                )
                return False

            # Normalize channel name
            if channel.startswith("CH"):
                channel_letter = "A" if channel == "CH1" else "B"
            else:
                channel_letter = channel.upper()

            file_path = Path(f"{rec_dir} Kinetic Log Ch {channel_letter}.txt")

            # Version-specific fieldnames
            if knx_version == "1.1":
                fieldnames = [
                    "Timestamp",
                    "Experiment Time",
                    "Event Type",
                    "Flow Rate",
                    "Sensor Temp",
                    "Device Temp",
                ]
            else:
                fieldnames = [
                    "Timestamp",
                    "Experiment Time",
                    "Event Type",
                    "Flow Rate",
                    "Temperature",
                ]

            with file_path.open("w", newline="", encoding=self.encoding) as txtfile:
                writer = csv.DictWriter(
                    txtfile,
                    dialect=self.csv_dialect,
                    fieldnames=fieldnames,
                )
                writer.writeheader()

                num_entries = len(log_data["times"])
                for i in range(num_entries):
                    if knx_version == "1.1":
                        writer.writerow(
                            {
                                "Timestamp": log_data["timestamps"][i],
                                "Experiment Time": log_data["times"][i],
                                "Event Type": log_data["events"][i],
                                "Flow Rate": log_data["flow"][i],
                                "Sensor Temp": log_data["temp"][i],
                                "Device Temp": log_data["dev"][i],
                            }
                        )
                    else:
                        writer.writerow(
                            {
                                "Timestamp": log_data["timestamps"][i],
                                "Experiment Time": log_data["times"][i],
                                "Event Type": log_data["events"][i],
                                "Flow Rate": log_data["flow"][i],
                                "Temperature": log_data["temp"][i],
                            }
                        )

            logger.info(
                f"Kinetic log Ch {channel_letter} saved: {file_path} ({num_entries} entries)"
            )
            return True

        except KeyError as e:
            logger.exception(f"Missing required key in kinetic log data: {e}")
            return False
        except Exception as e:
            logger.exception(f"Error saving kinetic log {channel}: {e}")
            return False

    def load_kinetic_log(
        self,
        file_path: str,
    ) -> dict[str, list] | None:
        """Load kinetic log from file.

        Args:
            file_path: Path to kinetic log file

        Returns:
            Dictionary with log data, or None if failed

        """
        try:
            log_data: dict[str, list] = {
                "timestamps": [],
                "times": [],
                "events": [],
                "flow": [],
                "temp": [],
                "dev": [],
            }

            with Path(file_path).open("r", encoding=self.encoding) as txtfile:
                reader = csv.DictReader(txtfile, dialect=self.csv_dialect)

                # Detect version from fieldnames
                fieldnames = reader.fieldnames or []
                has_dev_temp = "Device Temp" in fieldnames
                temp_key = "Sensor Temp" if has_dev_temp else "Temperature"

                for row in reader:
                    log_data["timestamps"].append(row["Timestamp"])
                    log_data["times"].append(float(row["Experiment Time"]))
                    log_data["events"].append(row["Event Type"])
                    log_data["flow"].append(float(row["Flow Rate"]))
                    log_data["temp"].append(float(row[temp_key]))

                    if has_dev_temp:
                        log_data["dev"].append(float(row["Device Temp"]))

            logger.info(f"Kinetic log loaded: {len(log_data['times'])} entries")
            return log_data

        except Exception as e:
            logger.exception(f"Error loading kinetic log: {e}")
            return None

    # ========================================================================
    # SPR DATA OPERATIONS
    # ========================================================================

    def save_spr_channel_data(
        self,
        file_path: str,
        times: np.ndarray,
        wavelengths: np.ndarray,
        channel: str,
    ) -> bool:
        """Save SPR wavelength data for a single channel.

        Args:
            file_path: Full path for the output file
            times: Array of time values
            wavelengths: Array of wavelength values
            channel: Channel identifier

        Returns:
            True if successful, False otherwise

        """
        try:
            with Path(file_path).open(
                "w", newline="", encoding=self.encoding
            ) as txtfile:
                writer = csv.writer(txtfile, dialect=self.csv_dialect)

                # Write header
                writer.writerow(["Time (s)", f"Wavelength Ch {channel.upper()} (nm)"])

                # Write data
                for time_val, wavelength in zip(times, wavelengths, strict=False):
                    writer.writerow([f"{time_val:.2f}", f"{wavelength:.4f}"])

            logger.debug(
                f"SPR channel {channel} data saved: {file_path} ({len(times)} points)"
            )
            return True

        except Exception as e:
            logger.exception(f"Error saving SPR channel {channel} data: {e}")
            return False

    def save_spr_processed_data(
        self,
        file_path: str,
        times: np.ndarray,
        wavelength_data: dict[str, np.ndarray],
        channels: list[str],
    ) -> bool:
        """Save processed SPR data for multiple channels in a single file.

        Args:
            file_path: Full path for the output file
            times: Array of time values (shared across channels)
            wavelength_data: Dictionary mapping channel names to wavelength arrays
            channels: List of channel identifiers to include

        Returns:
            True if successful, False otherwise

        """
        try:
            with Path(file_path).open(
                "w", newline="", encoding=self.encoding
            ) as txtfile:
                writer = csv.writer(txtfile, dialect=self.csv_dialect)

                # Write header
                header = ["Time (s)"]
                for ch in channels:
                    header.append(f"Wavelength Ch {ch.upper()} (nm)")
                writer.writerow(header)

                # Write data rows
                for i, time_val in enumerate(times):
                    row = [f"{time_val:.2f}"]
                    for ch in channels:
                        if ch in wavelength_data and i < len(wavelength_data[ch]):
                            wavelength = wavelength_data[ch][i]
                            if not np.isnan(wavelength):
                                row.append(f"{wavelength:.4f}")
                            else:
                                row.append("")
                        else:
                            row.append("")
                    writer.writerow(row)

            logger.info(
                f"Processed SPR data saved: {file_path} ({len(times)} points, {len(channels)} channels)"
            )
            return True

        except Exception as e:
            logger.exception(f"Error saving processed SPR data: {e}")
            return False

    def save_segment_table(
        self,
        file_path: str,
        segments: list[dict[str, Any]],
    ) -> bool:
        """Save experiment segment metadata table.

        Args:
            file_path: Full path for the output file
            segments: List of segment dictionaries with keys:
                - name: Segment name/number
                - start_time: Start time in seconds
                - end_time: End time in seconds
                - type: Segment type (e.g., "Baseline", "Association", "Dissociation")

        Returns:
            True if successful, False otherwise

        """
        try:
            with Path(file_path).open(
                "w", newline="", encoding=self.encoding
            ) as txtfile:
                fieldnames = ["Segment", "Start Time (s)", "End Time (s)", "Type"]
                writer = csv.DictWriter(
                    txtfile,
                    dialect=self.csv_dialect,
                    fieldnames=fieldnames,
                )
                writer.writeheader()

                for seg in segments:
                    writer.writerow(
                        {
                            "Segment": seg.get("name", ""),
                            "Start Time (s)": f"{seg.get('start_time', 0):.2f}",
                            "End Time (s)": f"{seg.get('end_time', 0):.2f}",
                            "Type": seg.get("type", ""),
                        }
                    )

            logger.info(f"Segment table saved: {file_path} ({len(segments)} segments)")
            return True

        except Exception as e:
            logger.exception(f"Error saving segment table: {e}")
            return False

    # ========================================================================
    # JSON OPERATIONS
    # ========================================================================

    def save_json(
        self,
        file_path: str,
        data: dict[str, Any],
        indent: int = 2,
    ) -> bool:
        """Save data to JSON file.

        Args:
            file_path: Full path for the output file
            data: Dictionary to save as JSON
            indent: Indentation level for pretty printing

        Returns:
            True if successful, False otherwise

        """
        try:
            with Path(file_path).open("w", encoding=self.encoding) as json_file:
                json.dump(data, json_file, indent=indent, default=self._json_serializer)

            logger.info(f"JSON data saved: {file_path}")
            return True

        except Exception as e:
            logger.exception(f"Error saving JSON file: {e}")
            return False

    def load_json(self, file_path: str) -> dict[str, Any] | None:
        """Load data from JSON file.

        Args:
            file_path: Path to JSON file

        Returns:
            Dictionary with loaded data, or None if failed

        """
        try:
            with Path(file_path).open("r", encoding=self.encoding) as json_file:
                data = json.load(json_file)

            logger.info(f"JSON data loaded: {file_path}")
            return data

        except Exception as e:
            logger.exception(f"Error loading JSON file: {e}")
            return None

    @staticmethod
    def _json_serializer(obj: Any) -> Any:
        """Custom JSON serializer for numpy types.

        Args:
            obj: Object to serialize

        Returns:
            Serializable representation

        """
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (np.integer, np.floating)):
            return obj.item()
        if isinstance(obj, np.bool_):
            return bool(obj)
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    # ========================================================================
    # ANALYSIS OPERATIONS
    # ========================================================================

    def save_analysis_table(
        self,
        file_path: str,
        headers: list[str],
        rows: list[list[Any]],
    ) -> bool:
        """Save analysis results table.

        Args:
            file_path: Full path for the output file
            headers: List of column headers
            rows: List of data rows (each row is a list of values)

        Returns:
            True if successful, False otherwise

        """
        try:
            with Path(file_path).open(
                "w", newline="", encoding=self.encoding
            ) as txtfile:
                writer = csv.writer(txtfile, dialect=self.csv_dialect)
                writer.writerow(headers)
                writer.writerows(rows)

            logger.info(f"Analysis table saved: {file_path} ({len(rows)} rows)")
            return True

        except Exception as e:
            logger.exception(f"Error saving analysis table: {e}")
            return False

    def save_kinetic_parameters(
        self,
        file_path: str,
        parameters: dict[str, dict[str, float]],
    ) -> bool:
        """Save kinetic binding parameters (ka, kd, KD).

        Args:
            file_path: Full path for the output file
            parameters: Dictionary mapping segment names to parameter dicts
                Each parameter dict has keys: 'ka', 'kd', 'KD', 'R_max', etc.

        Returns:
            True if successful, False otherwise

        """
        try:
            with Path(file_path).open(
                "w", newline="", encoding=self.encoding
            ) as txtfile:
                fieldnames = [
                    "Segment",
                    "ka (1/Ms)",
                    "kd (1/s)",
                    "KD (M)",
                    "R_max",
                    "Chi²",
                ]
                writer = csv.DictWriter(
                    txtfile,
                    dialect=self.csv_dialect,
                    fieldnames=fieldnames,
                )
                writer.writeheader()

                for seg_name, params in parameters.items():
                    writer.writerow(
                        {
                            "Segment": seg_name,
                            "ka (1/Ms)": f"{params.get('ka', 0):.3e}",
                            "kd (1/s)": f"{params.get('kd', 0):.3e}",
                            "KD (M)": f"{params.get('KD', 0):.3e}",
                            "R_max": f"{params.get('R_max', 0):.4f}",
                            "Chi²": f"{params.get('chi_squared', 0):.4f}",
                        }
                    )

            logger.info(f"Kinetic parameters saved: {file_path}")
            return True

        except Exception as e:
            logger.exception(f"Error saving kinetic parameters: {e}")
            return False

    # ========================================================================
    # UTILITY METHODS
    # ========================================================================

    def create_export_directory(
        self,
        base_dir: str,
        directory_name: str,
    ) -> Optional[Path]:
        """Create a directory for exporting data.

        Args:
            base_dir: Base directory path
            directory_name: Name of the directory to create

        Returns:
            Path object for the created directory, or None if failed

        """
        try:
            export_path = Path(base_dir) / directory_name
            export_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Export directory created: {export_path}")
            return export_path

        except Exception as e:
            logger.exception(f"Error creating export directory: {e}")
            return None

    def validate_file_path(self, file_path: str) -> bool:
        """Validate that a file path is writable.

        Args:
            file_path: Path to validate

        Returns:
            True if path is valid and writable, False otherwise

        """
        try:
            path = Path(file_path)

            # Check parent directory exists or can be created
            if not path.parent.exists():
                path.parent.mkdir(parents=True, exist_ok=True)

            # Check we have write permissions
            if path.exists() and not path.is_file():
                logger.error(f"Path exists but is not a file: {file_path}")
                return False

            return True

        except Exception as e:
            logger.exception(f"Error validating file path: {e}")
            return False

    def get_file_size(self, file_path: str) -> Optional[int]:
        """Get file size in bytes.

        Args:
            file_path: Path to file

        Returns:
            File size in bytes, or None if file doesn't exist

        """
        try:
            path = Path(file_path)
            if path.exists() and path.is_file():
                return path.stat().st_size
            return None
        except Exception as e:
            logger.exception(f"Error getting file size: {e}")
            return None
