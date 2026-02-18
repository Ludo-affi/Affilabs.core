from __future__ import annotations

# ruff: noqa: PLR0912, PLR0915, C901, BLE001

"""ExportMixin for DataWindow — extracted from affilabs/widgets/datawindow.py.

Included methods:
    - export_trigger       (datawindow.py L2545-L2547)
    - export_raw_data      (datawindow.py L2549-L2713)
    - export_to_excel      (datawindow.py L2715-L2791)
    - export_table         (datawindow.py L2794-L3027)
    - save_data            (datawindow.py L3109-L3170)
    - start_recording      (datawindow.py L3172-L3181)
    - add_recording_marker (datawindow.py L3185-L3224)
"""

import csv
import datetime
from bisect import bisect_left
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing_extensions import Self
else:
    try:
        from typing import Self
    except ImportError:
        from typing_extensions import Self

import numpy as np
import pandas as pd
from PySide6.QtWidgets import QFileDialog

# Replicate TIME_ZONE constant from datawindow.py
try:
    from datetime import UTC
except ImportError:
    from datetime import timezone
    UTC = timezone.utc

TIME_ZONE = datetime.datetime.now(UTC).astimezone().tzinfo

from affilabs.utils.data_exporter import DataExporter
from affilabs.utils.logger import logger
from affilabs.widgets.message import show_message
from affilabs.widgets.metadata import MetadataPrompt
from settings import CH_LIST, SW_VERSION


class ExportMixin:
    """Mixin providing all data-export and recording methods for DataWindow.

    Covers raw-data export (tab-separated text), Excel export, cycle-table
    export, auto-save on recording stop, recording start/reset, and the
    recording-start visual marker on the sensorgram.
    """

    def export_trigger(self: Self) -> None:
        """Export trigger."""
        self.save_sig.emit()

    def export_raw_data(
        self: Self,
        *,
        preset: bool = False,
        preset_dir: str | Path = "",
    ) -> None:
        """Export raw data."""
        try:
            error = True
            if preset:
                file_name = preset_dir
            else:
                if self.metadata.show_on_save:
                    metadata_prompt = MetadataPrompt(self.metadata, self)
                    if not metadata_prompt.exec():
                        show_message("Data export aborted", "Warning")
                        return
                file_name = QFileDialog.getSaveFileName(
                    self,
                    "Export Raw Data to file",
                )[0]
            full_file = f"{file_name} Raw Data.txt"

            if full_file not in {" Raw Data.txt", "/Recording Raw Data.txt"}:
                error = False

                with Path(full_file).open("w", newline="", encoding="utf-8") as txtfile:
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
                    writer = csv.DictWriter(
                        txtfile,
                        dialect="excel-tab",
                        fieldnames=fieldnames,
                    )

                    l_val_data = deepcopy(self.data["lambda_values"])
                    l_time_data = deepcopy(self.data["lambda_times"])

                    # Finds the first time greater than or equal to 0 on the first
                    # channel to use as a reference point
                    reference_index = bisect_left(l_time_data[CH_LIST[0]], 0)
                    # Clamp to valid range - check minimum length across ALL channels
                    min_array_len = min(len(l_val_data[ch]) for ch in CH_LIST)
                    if min_array_len == 0:
                        logger.error("Cannot export: no data in lambda_values")
                        return
                    reference_index = min(reference_index, min_array_len - 1)
                    logger.debug(
                        f"Export reference index: {reference_index} (min array length: {min_array_len})",
                    )
                    references = [l_val_data[ch][reference_index] for ch in CH_LIST]

                    row_count = min(len(x) for x in l_time_data.values())

                    self.metadata.write_tracedrawer_header(
                        writer,
                        fieldnames,
                        "Raw data",
                        references,
                    )

                    # Build DataFrame for vectorized CSV writing
                    row_count = min(len(x) for x in l_time_data.values())

                    # Prepare data dictionary
                    data_dict = {}
                    for i, ch in enumerate(CH_LIST):
                        data_dict[f"X_RawData{ch.upper()}"] = np.round(
                            l_time_data[ch][:row_count],
                            4,
                        )
                        # Convert wavelength to shift (nm) using reference
                        values = l_val_data[ch][:row_count]
                        data_dict[f"Y_RawData{ch.upper()}"] = np.round(
                            (values - references[i]) * 355,
                            4,
                        )

                    # Create DataFrame and write to CSV
                    df = pd.DataFrame(data_dict)
                    df.replace({np.nan: None}, inplace=True)
                    df.to_csv(
                        txtfile,
                        sep="\t",
                        index=False,
                        header=False,
                        encoding="utf-8",
                    )

            if self.data["filt"]:
                full_file = f"{preset_dir} Filtered Data.txt"
                if full_file not in {
                    " Filtered Data.txt",
                    "/Recording Filtered Data.txt",
                }:
                    error = False
                    with Path(full_file).open(
                        "w",
                        newline="",
                        encoding="utf-8",
                    ) as txtfile:
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
                        writer = csv.DictWriter(
                            txtfile,
                            dialect="excel-tab",
                            fieldnames=fieldnames,
                        )
                        writer.writeheader()

                        l_val_data = deepcopy(self.data["filtered_lambda_values"])
                        l_time_data = deepcopy(self.data["buffered_lambda_times"])

                        row_count = min(len(l_time_data[ch]) for ch in CH_LIST)

                        # Build DataFrame for vectorized CSV writing
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

                        # Create DataFrame and write to CSV
                        df = pd.DataFrame(data_dict)
                        df.replace({np.nan: None}, inplace=True)
                        df.to_csv(
                            txtfile,
                            sep="\t",
                            index=False,
                            header=False,
                            encoding="utf-8",
                        )
            if error:
                self.export_error_signal.emit()
            elif not preset:
                show_message(
                    msg="Sensorgram data exported",
                    msg_type="Info",
                    auto_close_time=3,
                )

        except Exception as e:
            logger.exception(f"export raw data error: {e}")
            self.export_error_signal.emit()

    def export_to_excel(self: Self) -> None:
        """Export data to Excel format with multiple sheets (pandas-based)."""
        try:
            # Get file location from user
            file_name = QFileDialog.getSaveFileName(
                self,
                "Export Data to Excel",
                "",
                "Excel Files (*.xlsx)",
            )[0]

            if not file_name:
                return  # User cancelled

            # Ensure .xlsx extension
            if not file_name.endswith(".xlsx"):
                file_name += ".xlsx"

            # Prepare data from existing data structure
            l_val_data = deepcopy(self.data["lambda_values"])
            l_time_data = deepcopy(self.data["lambda_times"])

            # Check if data is available
            min_array_len = min(len(l_val_data[ch]) for ch in CH_LIST)
            if min_array_len == 0:
                logger.error("Cannot export: no data available")
                show_message("No data to export", "Warning")
                return

            # Create raw data in LONG format (each channel has its own timestamp)
            # CRITICAL: Channels are measured in SERIES not PARALLEL
            raw_data_rows = []
            for ch in CH_LIST:
                ch_times = l_time_data[ch]
                ch_wavelengths = l_val_data[ch]
                for t, w in zip(ch_times, ch_wavelengths):
                    raw_data_rows.append({
                        'time': round(t, 4),
                        'channel': ch,
                        'value': round(w, 4)
                    })

            df_raw = pd.DataFrame(raw_data_rows)

            # Create Excel writer
            with pd.ExcelWriter(file_name, engine="openpyxl") as writer:
                # Write raw data
                df_raw.to_excel(writer, sheet_name="Raw Data", index=False)

                # Add filtered data if available (also in long format)
                if self.data["filt"]:
                    l_val_filt = deepcopy(self.data["filtered_lambda_values"])
                    l_time_filt = deepcopy(self.data["buffered_lambda_times"])

                    filtered_data_rows = []
                    for ch in CH_LIST:
                        ch_times = l_time_filt[ch]
                        ch_wavelengths = l_val_filt[ch]
                        for t, w in zip(ch_times, ch_wavelengths):
                            filtered_data_rows.append({
                                'time': round(t, 4),
                                'channel': ch,
                                'value': round(w, 4)
                            })

                    df_filt = pd.DataFrame(filtered_data_rows)
                    df_filt.to_excel(writer, sheet_name="Filtered Data", index=False)

            show_message(
                msg=f"Data exported to Excel:\n{Path(file_name).name}",
                msg_type="Info",
                auto_close_time=3,
            )

        except Exception as e:
            logger.exception(f"Excel export error: {e}")
            show_message(f"Excel export failed: {e}", "Error")

    # export table data
    def export_table(
        self: Self,
        *,
        preset: bool = False,
        preset_dir: str | None = None,
    ) -> None:
        """Export table data using pandas."""
        try:
            if len(self.saved_segments) == 0:
                show_message("No segments to export", "Warning")
                return

            error = True
            if preset:
                dir_path = preset_dir
                file_name = f"{dir_path}"
            else:
                file_name = QFileDialog.getSaveFileName(
                    self,
                    "Export Cycle Data Table to file, with segments data",
                )[0]
            full_file = f"{file_name} Cycle Data Table.txt"

            if full_file not in {
                " Cycle Data Table.txt",
                "/Recording Cycle Data Table.txt",
            }:
                error = False
                # Use pandas to export table data
                self.saved_segments.to_csv(full_file, encoding="utf-8")

                for seg in self.saved_segments:
                    with Path(f"{file_name} Cycle{seg.name}.txt").open(
                        "w",
                        newline="",
                        encoding="utf-8",
                    ) as txtfile:
                        fieldnames = [
                            f"X_Cyc{seg.name}_ChA",
                            f"Y_Cyc{seg.name}_ChA",
                            f"X_Cyc{seg.name}_ChB",
                            f"Y_Cyc{seg.name}_ChB",
                            f"X_Cyc{seg.name}_ChC",
                            f"Y_Cyc{seg.name}_ChC",
                            f"X_Cyc{seg.name}_ChD",
                            f"Y_Cyc{seg.name}_ChD",
                        ]
                        writer = csv.DictWriter(
                            txtfile,
                            dialect="excel-tab",
                            fieldnames=fieldnames,
                        )
                        writer.writerow({fieldnames[0]: "Plot name"})
                        writer.writerow(
                            {fieldnames[0]: "Plot xlabel", fieldnames[1]: "Time (s)"},
                        )
                        writer.writerow(
                            {
                                fieldnames[0]: "Plot ylabel",
                                fieldnames[1]: f"{self.unit}",
                            },
                        )
                        writer.writerow(
                            {
                                fieldnames[0]: "Property Analysis temp",
                                fieldnames[1]: "0.0",
                            },
                        )
                        now = datetime.datetime.now(TIME_ZONE)
                        writer.writerow(
                            {
                                fieldnames[0]: "Property Analysis date",
                                fieldnames[
                                    1
                                ]: f"{now.year:04d}-{now.month:02d}-{now.day:02d} "
                                f"{now.hour:02d}:{now.minute:02d}:{now.second:02d}",
                            },
                        )
                        writer.writerow(
                            {
                                fieldnames[0]: "Property Filename",
                                fieldnames[1]: f"Cycle{seg.name}",
                            },
                        )
                        writer.writerow(
                            {
                                fieldnames[0]: "Property Instrument id",
                                fieldnames[1]: "N/A",
                            },
                        )
                        writer.writerow(
                            {
                                fieldnames[0]: "Property Instrument type",
                                fieldnames[1]: "Affinite SPR",
                            },
                        )
                        writer.writerow(
                            {
                                fieldnames[0]: "Property Software",
                                fieldnames[1]: f"ezControl {SW_VERSION}",
                            },
                        )
                        writer.writerow(
                            {
                                fieldnames[0]: "Property Solid support",
                                fieldnames[1]: "N/A",
                            },
                        )
                        writer.writerow(
                            {
                                fieldnames[0]: "Curve",
                                fieldnames[1]: 1,
                                fieldnames[2]: "Curve",
                                fieldnames[3]: 2,
                                fieldnames[4]: "Curve",
                                fieldnames[5]: 3,
                                fieldnames[6]: "Curve",
                                fieldnames[7]: 4,
                            },
                        )
                        writer.writerow(
                            {
                                fieldnames[0]: "Curve name",
                                fieldnames[1]: f"{seg.note} Ch A",
                                fieldnames[2]: "Curve name",
                                fieldnames[3]: f"{seg.note} Ch B",
                                fieldnames[4]: "Curve name",
                                fieldnames[5]: f"{seg.note} Ch C",
                                fieldnames[6]: "Curve name",
                                fieldnames[7]: f"{seg.note} Ch D",
                            },
                        )
                        writer.writerow(
                            {
                                fieldnames[0]: "Curve type",
                                fieldnames[1]: "Curve",
                                fieldnames[2]: "Curve type",
                                fieldnames[3]: "Curve",
                                fieldnames[4]: "Curve type",
                                fieldnames[5]: "Curve",
                                fieldnames[6]: "Curve type",
                                fieldnames[7]: "Curve",
                            },
                        )
                        writer.writerow(
                            {
                                fieldnames[0]: "Curve ligand",
                                fieldnames[1]: "N/A",
                                fieldnames[2]: "Curve ligand",
                                fieldnames[3]: "N/A",
                                fieldnames[4]: "Curve ligand",
                                fieldnames[5]: "N/A",
                                fieldnames[6]: "Curve ligand",
                                fieldnames[7]: "N/A",
                            },
                        )
                        writer.writerow(
                            {
                                fieldnames[0]: "Curve concentration (M)",
                                fieldnames[1]: "0.0E-8",
                                fieldnames[2]: "Curve concentration (M)",
                                fieldnames[3]: "0.0E-8",
                                fieldnames[4]: "Curve concentration (M)",
                                fieldnames[5]: "0.0E-8",
                                fieldnames[6]: "Curve concentration (M)",
                                fieldnames[7]: "0.0E-8",
                            },
                        )
                        writer.writerow(
                            {
                                fieldnames[0]: "Curve target",
                                fieldnames[1]: "N/A",
                                fieldnames[2]: "Curve target",
                                fieldnames[3]: "N/A",
                                fieldnames[4]: "Curve target",
                                fieldnames[5]: "N/A",
                                fieldnames[6]: "Curve target",
                                fieldnames[7]: "N/A",
                            },
                        )
                        writer.writerow(
                            {
                                fieldnames[0]: "Curve description",
                                fieldnames[1]: f"Cycle {seg.name} Ch A",
                                fieldnames[2]: "Curve description",
                                fieldnames[3]: f"Cycle {seg.name} Ch B",
                                fieldnames[4]: "Curve description",
                                fieldnames[5]: f"Cycle {seg.name} Ch C",
                                fieldnames[6]: "Curve description",
                                fieldnames[7]: f"Cycle {seg.name} Ch D",
                            },
                        )
                        writer.writerow(
                            {
                                fieldnames[0]: "X",
                                fieldnames[1]: "Y",
                                fieldnames[2]: "X",
                                fieldnames[3]: "Y",
                                fieldnames[4]: "X",
                                fieldnames[5]: "Y",
                                fieldnames[6]: "X",
                                fieldnames[7]: "Y",
                            },
                        )

                        row_count = len(seg.seg_x["a"])
                        for ch in CH_LIST:
                            row_count = min(len(seg.seg_x[ch]), row_count)

                        for j in range(row_count):
                            for ch in CH_LIST:
                                if np.isnan(seg.seg_y[ch][j]):
                                    seg.seg_y[ch][j] = None
                            writer.writerow(
                                {
                                    f"X_Cyc{seg.name}_ChA": round(seg.seg_x["a"][j], 4),
                                    f"Y_Cyc{seg.name}_ChA": round(seg.seg_y["a"][j], 4),
                                    f"X_Cyc{seg.name}_ChB": round(seg.seg_x["b"][j], 4),
                                    f"Y_Cyc{seg.name}_ChB": round(seg.seg_y["b"][j], 4),
                                    f"X_Cyc{seg.name}_ChC": round(seg.seg_x["c"][j], 4),
                                    f"Y_Cyc{seg.name}_ChC": round(seg.seg_y["c"][j], 4),
                                    f"X_Cyc{seg.name}_ChD": round(seg.seg_x["d"][j], 4),
                                    f"Y_Cyc{seg.name}_ChD": round(seg.seg_y["d"][j], 4),
                                },
                            )
                if not preset:
                    show_message(msg="Cycle data exported")

            if error:
                self.export_error_signal.emit()

        except Exception as e:
            logger.exception(f"export table error: {e}")
            self.export_error_signal.emit()

    def save_data(self: Self, rec_dir: str) -> None:
        """Save data using centralized DataExporter."""
        try:
            # Extract experiment name from rec_dir
            from pathlib import Path

            rec_path = Path(rec_dir)
            exp_name = rec_path.name if rec_path.name else "Recording"

            # Create DataExporter instance
            exporter = DataExporter(base_dir=rec_dir, experiment_name=exp_name)

            # Export raw data
            try:
                exporter.export_raw_data(
                    data=self.data,
                    metadata=self.metadata,
                    references=None,  # Will auto-calculate
                )
            except Exception as e:
                logger.error(f"Failed to export raw data: {e}")

            # Export filtered data if available
            if self.data.get("filt", False):
                try:
                    # Create filtered data dict
                    filtered_data = {
                        "lambda_times": self.data.get(
                            "buffered_lambda_times",
                            self.data["lambda_times"],
                        ),
                        "lambda_values": self.data.get(
                            "filtered_lambda_values",
                            self.data["lambda_values"],
                        ),
                        "filt": True,
                    }
                    exporter.export_filtered_data(
                        data=filtered_data,
                        metadata=self.metadata,
                    )
                except Exception as e:
                    logger.error(f"Failed to export filtered data: {e}")

            # Export segments
            try:
                segments = [seg.to_dict() for seg in self.segment_list]
                if segments:
                    exporter.export_segments(
                        segments=segments,
                        value_list=self.data["lambda_values"],
                        ts_list=self.data["lambda_times"],
                    )
            except Exception as e:
                logger.error(f"Failed to export segments: {e}")

            # Save manifest
            exporter.save_manifest()
            logger.info(f"Data export completed to {rec_dir}")

        except Exception as e:
            logger.exception(f"Error in save_data: {e}")

    def start_recording(self: Self, rec_dir: str) -> None:
        """Start recording."""
        # Reset time reference so timestamps start at zero
        self.full_segment_view.reset_time()
        self.live_segment_start = None

        # Move yellow cursor (right) to 0
        self.full_segment_view.set_right(0, emit=False, update=False)
        logger.debug("Recording started: time reset to zero")
        self.new_segment()
        # Don't save data yet - wait for set_start() to adjust timestamps
        # self.save_data(rec_dir) will be called after timestamps are adjusted

    def add_recording_marker(self, time_position: float) -> None:
        """Add vertical line marker on graph showing where recording started.

        Args:
            time_position: Elapsed time (seconds) when recording started
        """
        try:
            import pyqtgraph as pg
            from PySide6.QtGui import QColor
            from PySide6.QtCore import Qt

            # Create vertical line at recording start time
            marker = pg.InfiniteLine(
                pos=time_position,
                angle=90,  # Vertical line
                pen=pg.mkPen(color=QColor(34, 139, 34), width=2, style=Qt.DashLine),
                movable=False,
                label='REC',
                labelOpts={
                    'position': 0.95,
                    'color': (34, 139, 34),
                    'fill': (255, 255, 255, 200),
                    'movable': False
                }
            )

            # Add to full timeline graph
            # Note: full_segment_view is the actual PlotWidget inside DataWindow
            if hasattr(self, 'full_segment_view') and self.full_segment_view:
                # Store reference to remove later if needed
                if not hasattr(self, '_recording_markers'):
                    self._recording_markers = []
                self._recording_markers.append(marker)

                # Add to plot - PlotWidget has addItem method
                self.full_segment_view.addItem(marker)
                logger.debug(f"Added recording marker at t={time_position:.1f}s")

        except Exception as e:
            logger.warning(f"Failed to add recording marker: {e}")
