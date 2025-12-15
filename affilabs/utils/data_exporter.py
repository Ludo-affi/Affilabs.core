from __future__ import annotations

"""Centralized data export service with validation and atomic writes.

This module provides a robust data export system with:
- Atomic file writes (temp file + rename)
- Data validation before export
- Export manifest generation
- Standardized file naming
- Checksum verification
"""

import csv
import hashlib
import json
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

import numpy as np
import pandas as pd

from affilabs.utils.logger import logger
from settings import CH_LIST, SW_VERSION


class ExportFormat(Enum):
    """Supported export formats."""

    TRACEDRAWER = "tracedrawer"  # With metadata headers
    CSV_SIMPLE = "csv_simple"  # Plain CSV without metadata
    CSV_EXCEL = "csv_excel"  # Excel-compatible CSV


@dataclass
class ExportedFile:
    """Record of an exported file."""

    filepath: str
    format: str
    checksum: str
    row_count: int
    timestamp: str
    size_bytes: int


@dataclass
class ExportPreset:
    """Define what to export."""

    name: str
    include_raw: bool = True
    include_filtered: bool = False
    include_segments: bool = True
    include_temperature: bool = True
    include_kinetics: bool = True
    format: ExportFormat = ExportFormat.TRACEDRAWER
    compression: bool = False


# Predefined export presets
EXPORT_PRESETS = {
    "quick": ExportPreset(
        name="Quick Export",
        include_raw=True,
        include_filtered=False,
        include_segments=True,
        include_temperature=False,
        include_kinetics=False,
    ),
    "full": ExportPreset(
        name="Full Export",
        include_raw=True,
        include_filtered=True,
        include_segments=True,
        include_temperature=True,
        include_kinetics=True,
    ),
    "analysis": ExportPreset(
        name="For Analysis",
        include_raw=False,
        include_filtered=True,
        include_segments=True,
        format=ExportFormat.CSV_SIMPLE,
    ),
}


class DataValidator:
    """Validate data before export."""

    @staticmethod
    def validate_sensorgram(data: dict) -> tuple[bool, str]:
        """Check sensorgram data integrity.

        Args:
            data: Dictionary with 'lambda_times' and 'lambda_values' keys

        Returns:
            Tuple of (is_valid, error_message)

        """
        errors = []

        # Check structure
        required_keys = ["lambda_times", "lambda_values"]
        for key in required_keys:
            if key not in data:
                errors.append(f"Missing key: {key}")
                return (False, "; ".join(errors))

        # Check data consistency per channel
        for ch in CH_LIST:
            times = data["lambda_times"].get(ch, [])
            values = data["lambda_values"].get(ch, [])

            if len(times) != len(values):
                errors.append(
                    f"Ch {ch}: length mismatch (times={len(times)}, values={len(values)})",
                )

            if len(times) == 0:
                errors.append(f"Ch {ch}: no data")

            # Check for NaN/Inf
            if len(values) > 0 and np.any(~np.isfinite(values)):
                errors.append(f"Ch {ch}: contains NaN or Inf")

        return (len(errors) == 0, "; ".join(errors) if errors else "Valid")

    @staticmethod
    def validate_dataframe(df: pd.DataFrame, name: str) -> tuple[bool, str]:
        """Check DataFrame integrity.

        Args:
            df: DataFrame to validate
            name: Name for error messages

        Returns:
            Tuple of (is_valid, error_message)

        """
        if df is None:
            return (False, f"{name}: DataFrame is None")

        if df.empty:
            return (False, f"{name}: DataFrame is empty")

        # Check for all NaN columns
        all_nan_cols = [col for col in df.columns if df[col].isna().all()]
        if all_nan_cols:
            return (False, f"{name}: Columns with all NaN: {all_nan_cols}")

        return (True, "Valid")


class DataExporter:
    """Centralized data export service with validation and manifest generation."""

    def __init__(self, base_dir: str | Path, experiment_name: str) -> None:
        """Initialize exporter.

        Args:
            base_dir: Base directory for exports
            experiment_name: Name of the experiment/recording

        """
        self.base_dir = Path(base_dir)
        self.exp_name = experiment_name
        self.exported_files: list[ExportedFile] = []

        # Create directory structure
        self._create_directory_structure()

    def _create_directory_structure(self) -> None:
        """Create organized directory structure."""
        dirs = [
            self.base_dir,
            self.base_dir / "raw_data",
            self.base_dir / "filtered_data",
            self.base_dir / "segments",
            self.base_dir / "logs",
        ]

        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

    def _calculate_checksum(self, filepath: Path) -> str:
        """Calculate MD5 checksum of file.

        Args:
            filepath: Path to file

        Returns:
            MD5 checksum as hex string

        """
        md5 = hashlib.md5()
        try:
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    md5.update(chunk)
            return md5.hexdigest()
        except Exception as e:
            logger.error(f"Failed to calculate checksum for {filepath}: {e}")
            return ""

    def _atomic_write(self, filepath: Path, content_writer, encoding="utf-8") -> None:
        """Write file atomically using temp file + rename.

        Args:
            filepath: Target file path
            content_writer: Callable that takes file handle and writes content
            encoding: File encoding

        """
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding=encoding,
                dir=filepath.parent,
                delete=False,
                suffix=".tmp",
            ) as tmp_file:
                content_writer(tmp_file)
                tmp_path = Path(tmp_file.name)

            # Atomic rename
            tmp_path.replace(filepath)
            logger.debug(f"File written successfully: {filepath}")

        except Exception as e:
            logger.error(f"Failed to write file {filepath}: {e}")
            raise

    def _record_export(
        self,
        filepath: Path,
        format: ExportFormat,
        row_count: int,
    ) -> None:
        """Record exported file in manifest.

        Args:
            filepath: Path to exported file
            format: Export format used
            row_count: Number of data rows

        """
        try:
            self.exported_files.append(
                ExportedFile(
                    filepath=str(filepath.relative_to(self.base_dir)),
                    format=format.value,
                    checksum=self._calculate_checksum(filepath),
                    row_count=row_count,
                    timestamp=datetime.now().isoformat(),
                    size_bytes=filepath.stat().st_size if filepath.exists() else 0,
                ),
            )
        except Exception as e:
            logger.error(f"Failed to record export for {filepath}: {e}")

    def export_raw_data(
        self,
        data: dict,
        metadata=None,
        references: list | None = None,
    ) -> None:
        """Export raw sensorgram data with validation.

        Args:
            data: Dictionary with 'lambda_times' and 'lambda_values'
            metadata: Metadata widget for TraceDrawer headers (optional)
            references: Reference wavelengths for each channel (optional)

        """
        # Validate data
        is_valid, error_msg = DataValidator.validate_sensorgram(data)
        if not is_valid:
            logger.error(f"Raw data validation failed: {error_msg}")
            msg = f"Invalid raw data: {error_msg}"
            raise ValueError(msg)

        l_time_data = data["lambda_times"]
        l_val_data = data["lambda_values"]

        # Calculate references if not provided
        if references is None:
            from bisect import bisect_left

            reference_index = bisect_left(l_time_data[CH_LIST[0]], 0)
            min_array_len = min(len(l_val_data[ch]) for ch in CH_LIST)
            if min_array_len == 0:
                msg = "Cannot export: no data in lambda_values"
                raise ValueError(msg)
            reference_index = min(reference_index, min_array_len - 1)
            references = [l_val_data[ch][reference_index] for ch in CH_LIST]

        row_count = min(len(l_time_data[ch]) for ch in CH_LIST)

        # Build output filepath
        filepath = self.base_dir / "raw_data" / "raw_data.txt"

        def write_content(f) -> None:
            fieldnames = [
                "X_RawDataA",
                "Y_RawDataA",
                "X_RawDataB",
                "Y_RawDataB",
                "X_RawDataC",
                "Y_RawDataC",
                "X_RawDataD",
                "Y_RawDataD",
            ]
            writer = csv.DictWriter(f, dialect="excel-tab", fieldnames=fieldnames)

            # Write metadata header if available
            if metadata:
                metadata.write_tracedrawer_header(
                    writer,
                    fieldnames,
                    "Raw data",
                    references,
                )

            # Build DataFrame for vectorized writing
            data_dict = {}
            for i, ch in enumerate(CH_LIST):
                data_dict[f"X_RawData{ch.upper()}"] = np.round(
                    l_time_data[ch][:row_count],
                    4,
                )
                values = l_val_data[ch][:row_count]
                data_dict[f"Y_RawData{ch.upper()}"] = np.round(
                    (values - references[i]) * 355,
                    4,
                )

            df = pd.DataFrame(data_dict)
            df = df.replace({np.nan: None})
            df.to_csv(f, sep="\t", index=False, header=False)

        self._atomic_write(filepath, write_content)
        self._record_export(filepath, ExportFormat.TRACEDRAWER, row_count)
        logger.info(f"Exported raw data: {row_count} rows to {filepath}")

    def export_filtered_data(self, data: dict, metadata=None) -> None:
        """Export filtered sensorgram data with validation.

        Args:
            data: Dictionary with 'lambda_times' and 'lambda_values'
            metadata: Metadata widget for TraceDrawer headers (optional)

        """
        # Validate data
        is_valid, error_msg = DataValidator.validate_sensorgram(data)
        if not is_valid:
            logger.error(f"Filtered data validation failed: {error_msg}")
            msg = f"Invalid filtered data: {error_msg}"
            raise ValueError(msg)

        if not data.get("filt", False):
            logger.warning("Filtered data not available, skipping export")
            return

        l_time_data = data["lambda_times"]
        l_val_data = data["lambda_values"]
        row_count = min(len(l_time_data[ch]) for ch in CH_LIST)

        filepath = self.base_dir / "filtered_data" / "filtered_data.txt"

        def write_content(f) -> None:
            fieldnames = [
                "X_DataA",
                "Y_DataA",
                "X_DataB",
                "Y_DataB",
                "X_DataC",
                "Y_DataC",
                "X_DataD",
                "Y_DataD",
            ]
            writer = csv.DictWriter(f, dialect="excel-tab", fieldnames=fieldnames)

            if metadata:
                metadata.write_tracedrawer_header(
                    writer,
                    fieldnames,
                    "Filtered data",
                    [0, 0, 0, 0],
                )

            data_dict = {}
            for ch in CH_LIST:
                data_dict[f"X_Data{ch.upper()}"] = np.round(
                    l_time_data[ch][:row_count],
                    4,
                )
                data_dict[f"Y_Data{ch.upper()}"] = np.round(
                    l_val_data[ch][:row_count],
                    4,
                )

            df = pd.DataFrame(data_dict)
            df = df.replace({np.nan: None})
            df.to_csv(f, sep="\t", index=False, header=False)

        self._atomic_write(filepath, write_content)
        self._record_export(filepath, ExportFormat.TRACEDRAWER, row_count)
        logger.info(f"Exported filtered data: {row_count} rows to {filepath}")

    def export_segments(self, segments: list, value_list: dict, ts_list: dict) -> None:
        """Export segment data with validation.

        Args:
            segments: List of segment dictionaries
            value_list: Dictionary of value arrays per channel
            ts_list: Dictionary of timestamp arrays per channel

        """
        import re

        def sanitize_filename(name: str) -> str:
            """Remove/replace unsafe characters from filename."""
            name = re.sub(r'[<>:"/\\|?*]', "_", name)
            name = name.strip(". ")
            return name[:200] if name else "unnamed"

        if not segments:
            logger.warning("No segments to export")
            return

        # Export segments summary table
        summary_data = []
        for seg in segments:
            summary_data.append(
                {
                    "Name": seg["name"],
                    "StartTime": seg["start_ts"],
                    "EndTime": seg["end_ts"],
                    "ShiftA": seg.get("shift_a", ""),
                    "ShiftB": seg.get("shift_b", ""),
                    "ShiftC": seg.get("shift_c", ""),
                    "ShiftD": seg.get("shift_d", ""),
                    "ShiftM": seg.get("shift_m", ""),
                    "UserNote": seg.get("note", ""),
                },
            )

        summary_path = self.base_dir / "segments" / "segments_summary.csv"

        def write_summary(f) -> None:
            df = pd.DataFrame(summary_data)
            df.to_csv(f, sep="\t", index=False)

        self._atomic_write(summary_path, write_summary)
        self._record_export(summary_path, ExportFormat.CSV_SIMPLE, len(summary_data))

        # Export individual segment files
        for idx, seg in enumerate(segments, start=1):
            data = {ch: [] for ch in CH_LIST}

            for ch in CH_LIST:
                start_val = None
                for i, ts in enumerate(ts_list[ch]):
                    if seg["start_ts"] <= ts <= seg["end_ts"]:
                        if start_val is None:
                            start_val = value_list[ch][i]
                            start_time = ts_list[ch][i]
                        data[ch].append(
                            {
                                "ts": (ts - start_time),
                                "val": round(value_list[ch][i] - start_val, 3),
                            },
                        )

            # Fill blank cells
            max_len = max([len(v) for v in data.values()])
            for ch in CH_LIST:
                for _ in range(max_len - len(data[ch])):
                    data[ch].append({"ts": "", "val": ""})

            # Sanitize filename with sequential numbering
            safe_name = sanitize_filename(seg["name"])
            seg_filename = f"segment_{idx:03d}_{safe_name}.csv"
            seg_path = self.base_dir / "segments" / seg_filename

            def write_segment(f) -> None:
                headers = [
                    [
                        f"X_{seg['name']}_{ch}_{seg['start_ts']}",
                        f"Y_{seg['name']}_{ch}_{seg['start_ts']}",
                    ]
                    for ch in ["A", "B", "C", "D", "M"]
                ]
                writer = csv.writer(
                    f,
                    delimiter="\t",
                    quotechar="|",
                    quoting=csv.QUOTE_MINIMAL,
                )
                writer.writerow([h for sublist in headers for h in sublist])

                for i in range(max_len):
                    writer.writerow(
                        [
                            data["a"][i]["ts"],
                            data["a"][i]["val"],
                            data["b"][i]["ts"],
                            data["b"][i]["val"],
                            data["c"][i]["ts"],
                            data["c"][i]["val"],
                            data["d"][i]["ts"],
                            data["d"][i]["val"],
                            data.get("m", data["a"])[i]["ts"],
                            data.get("m", data["a"])[i]["val"],
                        ],
                    )

            self._atomic_write(seg_path, write_segment)
            self._record_export(seg_path, ExportFormat.CSV_SIMPLE, max_len)

        logger.info(f"Exported {len(segments)} segments")

    def export_temperature_log(self, temp_log: pd.DataFrame) -> None:
        """Export temperature log with validation.

        Args:
            temp_log: DataFrame with temperature data

        """
        is_valid, error_msg = DataValidator.validate_dataframe(
            temp_log,
            "Temperature log",
        )
        if not is_valid:
            logger.warning(f"Temperature log validation failed: {error_msg}")
            return

        filepath = self.base_dir / "logs" / "temperature_log.csv"

        def write_content(f) -> None:
            temp_log.to_csv(f, sep="\t", index=False)

        self._atomic_write(filepath, write_content)
        self._record_export(filepath, ExportFormat.CSV_SIMPLE, len(temp_log))
        logger.info(f"Exported temperature log: {len(temp_log)} rows")

    def export_kinetic_log(
        self,
        log_ch1: pd.DataFrame,
        log_ch2: pd.DataFrame | None = None,
        version: str = "1.0",
    ) -> None:
        """Export kinetic log(s) with validation.

        Args:
            log_ch1: DataFrame with channel 1 kinetic data
            log_ch2: DataFrame with channel 2 kinetic data (optional)
            version: Kinetic controller version for column naming

        """
        # Export Channel A
        is_valid, error_msg = DataValidator.validate_dataframe(
            log_ch1,
            "Kinetic log Ch1",
        )
        if not is_valid:
            logger.warning(f"Kinetic Ch1 validation failed: {error_msg}")
        else:
            filepath_ch1 = self.base_dir / "logs" / "kinetic_ch_a.csv"

            # Rename columns based on version
            if version == "1.1":
                ch1_export = log_ch1.rename(
                    columns={
                        "timestamp": "Timestamp",
                        "time": "Experiment Time",
                        "event": "Event Type",
                        "flow": "Flow Rate",
                        "temp": "Sensor Temp",
                        "dev": "Device Temp",
                    },
                )
            else:
                ch1_export = log_ch1.rename(
                    columns={
                        "timestamp": "Timestamp",
                        "time": "Experiment Time",
                        "event": "Event Type",
                        "flow": "Flow Rate",
                        "temp": "Temperature",
                    },
                )[
                    [
                        "Timestamp",
                        "Experiment Time",
                        "Event Type",
                        "Flow Rate",
                        "Temperature",
                    ]
                ]

            def write_ch1(f) -> None:
                ch1_export.to_csv(f, sep="\t", index=False)

            self._atomic_write(filepath_ch1, write_ch1)
            self._record_export(filepath_ch1, ExportFormat.CSV_SIMPLE, len(ch1_export))
            logger.info(f"Exported kinetic Ch A: {len(ch1_export)} rows")

        # Export Channel B if provided
        if log_ch2 is not None:
            is_valid, error_msg = DataValidator.validate_dataframe(
                log_ch2,
                "Kinetic log Ch2",
            )
            if not is_valid:
                logger.warning(f"Kinetic Ch2 validation failed: {error_msg}")
            else:
                filepath_ch2 = self.base_dir / "logs" / "kinetic_ch_b.csv"

                if version == "1.1":
                    ch2_export = log_ch2.rename(
                        columns={
                            "timestamp": "Timestamp",
                            "time": "Experiment Time",
                            "event": "Event Type",
                            "flow": "Flow Rate",
                            "temp": "Sensor Temp",
                            "dev": "Device Temp",
                        },
                    )
                else:
                    ch2_export = log_ch2.rename(
                        columns={
                            "timestamp": "Timestamp",
                            "time": "Experiment Time",
                            "event": "Event Type",
                            "flow": "Flow Rate",
                            "temp": "Temperature",
                        },
                    )[
                        [
                            "Timestamp",
                            "Experiment Time",
                            "Event Type",
                            "Flow Rate",
                            "Temperature",
                        ]
                    ]

                def write_ch2(f) -> None:
                    ch2_export.to_csv(f, sep="\t", index=False)

                self._atomic_write(filepath_ch2, write_ch2)
                self._record_export(
                    filepath_ch2,
                    ExportFormat.CSV_SIMPLE,
                    len(ch2_export),
                )
                logger.info(f"Exported kinetic Ch B: {len(ch2_export)} rows")

    def save_manifest(self) -> None:
        """Save export manifest with checksums for verification."""
        manifest = {
            "experiment": self.exp_name,
            "export_timestamp": datetime.now().isoformat(),
            "software_version": SW_VERSION,
            "total_files": len(self.exported_files),
            "files": [asdict(f) for f in self.exported_files],
        }

        manifest_path = self.base_dir / "export_manifest.json"

        def write_manifest(f) -> None:
            json.dump(manifest, f, indent=2)

        try:
            self._atomic_write(manifest_path, write_manifest)
            logger.info(f"Export manifest saved: {len(self.exported_files)} files")
        except Exception as e:
            logger.error(f"Failed to save export manifest: {e}")

    def save_metadata(self, device_config: dict, settings: dict) -> None:
        """Save experiment metadata.

        Args:
            device_config: Device configuration dictionary
            settings: Experiment settings dictionary

        """
        metadata = {
            "experiment_name": self.exp_name,
            "timestamp": datetime.now().isoformat(),
            "device": {
                "controller": device_config.get("ctrl", ""),
                "kinetic": device_config.get("knx", ""),
                "detector": device_config.get("detector", ""),
                "device_id": device_config.get("device_id", ""),
            },
            "settings": settings,
            "software_version": SW_VERSION,
        }

        metadata_path = self.base_dir / "experiment_metadata.json"

        def write_metadata(f) -> None:
            json.dump(metadata, f, indent=2)

        try:
            self._atomic_write(metadata_path, write_metadata)
            logger.info("Experiment metadata saved")
        except Exception as e:
            logger.error(f"Failed to save experiment metadata: {e}")
