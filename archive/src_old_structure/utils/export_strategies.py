"""Export Strategy Pattern Implementation for data export formats.

This module provides a clean Strategy Pattern implementation for exporting
SPR data to various formats (Excel, CSV, JSON, HDF5).

Usage:
    from utils.export_strategies import get_export_strategy

    exporter = get_export_strategy('excel')
    exporter.export(file_path, export_data, config)
"""

import logging

logger = logging.getLogger(__name__)


# ============================================================================
# Export Strategy Pattern Implementation
# ============================================================================


class ExportStrategy:
    """Base class for export strategies."""

    def export(self, file_path: str, export_data: dict, config: dict):
        """Export data to file.

        Args:
            file_path: Destination file path
            export_data: Dict of channel data with 'raw' and 'processed' DataFrames
            config: Export configuration dict

        """
        raise NotImplementedError("Subclasses must implement export()")

    def _build_metadata(self, config: dict) -> dict:
        """Build common metadata dict.

        Args:
            config: Export configuration

        Returns:
            Metadata dictionary

        """
        import datetime as dt

        return {
            "export_date": dt.datetime.now().strftime("%Y-%m-%d"),
            "export_time": dt.datetime.now().strftime("%H:%M:%S"),
            "format": config.get("format", "unknown"),
            "precision": config.get("precision", 4),
            "channels": ", ".join([c.upper() for c in config.get("channels", [])]),
        }


class ExcelExportStrategy(ExportStrategy):
    """Export strategy for Excel files."""

    def export(self, file_path: str, export_data: dict, config: dict):
        """Export data to Excel workbook with multiple sheets."""
        import pandas as pd

        with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
            # Export each channel's data
            for ch, ch_data in export_data.items():
                if "raw" in ch_data and not ch_data["raw"].empty:
                    sheet_name = f"Channel_{ch.upper()}_Raw"
                    ch_data["raw"].to_excel(writer, sheet_name=sheet_name, index=False)

                if "processed" in ch_data and not ch_data["processed"].empty:
                    sheet_name = f"Channel_{ch.upper()}_Processed"
                    ch_data["processed"].to_excel(
                        writer,
                        sheet_name=sheet_name,
                        index=False,
                    )

            # Add metadata sheet if requested
            if config.get("include_metadata", False):
                metadata = self._build_metadata(config)
                metadata_df = pd.DataFrame(
                    {
                        "Parameter": list(metadata.keys()),
                        "Value": list(metadata.values()),
                    },
                )
                metadata_df.to_excel(writer, sheet_name="Metadata", index=False)

        logger.info(f"Excel export complete: {file_path}")


class CSVExportStrategy(ExportStrategy):
    """Export strategy for CSV files."""

    def export(self, file_path: str, export_data: dict, config: dict):
        """Export data to CSV file (combines all channels)."""
        import pandas as pd

        # Combine all channels into one CSV
        combined_data = {}

        for ch, ch_data in export_data.items():
            if "raw" in ch_data and not ch_data["raw"].empty:
                df = ch_data["raw"]
                if "Time (s)" in df.columns:
                    if "Time (s)" not in combined_data:
                        combined_data["Time (s)"] = df["Time (s)"]
                    # Add SPR column
                    for col in df.columns:
                        if col != "Time (s)":
                            combined_data[col] = df[col]

        if combined_data:
            combined_df = pd.DataFrame(combined_data)
            combined_df.to_csv(file_path, index=False)
            logger.info(f"CSV export complete: {file_path}")


class JSONExportStrategy(ExportStrategy):
    """Export strategy for JSON files."""

    def export(self, file_path: str, export_data: dict, config: dict):
        """Export data to JSON file."""
        import datetime as dt
        import json

        # Convert DataFrames to dictionaries
        json_data = {}
        for ch, ch_data in export_data.items():
            json_data[f"channel_{ch}"] = {}
            if "raw" in ch_data and not ch_data["raw"].empty:
                json_data[f"channel_{ch}"]["raw"] = ch_data["raw"].to_dict("list")
            if "processed" in ch_data and not ch_data["processed"].empty:
                json_data[f"channel_{ch}"]["processed"] = ch_data["processed"].to_dict(
                    "list",
                )

        # Add metadata
        if config.get("include_metadata", False):
            metadata = self._build_metadata(config)
            json_data["metadata"] = {
                "export_date": dt.datetime.now().isoformat(),
                "format": metadata["format"],
                "precision": metadata["precision"],
                "channels": config.get("channels", []),
            }

        with open(file_path, "w") as f:
            json.dump(json_data, f, indent=2)

        logger.info(f"JSON export complete: {file_path}")


class HDF5ExportStrategy(ExportStrategy):
    """Export strategy for HDF5 files."""

    def export(self, file_path: str, export_data: dict, config: dict):
        """Export data to HDF5 file."""
        import pandas as pd

        with pd.HDFStore(file_path, mode="w") as store:
            for ch, ch_data in export_data.items():
                if "raw" in ch_data and not ch_data["raw"].empty:
                    store.put(f"channel_{ch}/raw", ch_data["raw"])
                if "processed" in ch_data and not ch_data["processed"].empty:
                    store.put(f"channel_{ch}/processed", ch_data["processed"])

        logger.info(f"HDF5 export complete: {file_path}")


# ============================================================================
# Factory Function
# ============================================================================


def get_export_strategy(format_type: str) -> ExportStrategy:
    """Factory function to get appropriate export strategy.

    Args:
        format_type: Export format ('excel', 'csv', 'json', 'hdf5')

    Returns:
        ExportStrategy instance for the specified format

    """
    strategies = {
        "excel": ExcelExportStrategy(),
        "csv": CSVExportStrategy(),
        "json": JSONExportStrategy(),
        "hdf5": HDF5ExportStrategy(),
    }
    return strategies.get(format_type, ExcelExportStrategy())
