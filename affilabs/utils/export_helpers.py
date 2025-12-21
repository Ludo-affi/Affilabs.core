"""Export Helper Utilities.

Provides export utility functions for:
- CSV export operations
- Cycle data autosaving
- Image export operations
- Data formatting and metadata

These are pure utility functions extracted from the main Application class.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from main_simplified import Application  # type: ignore[import-not-found]

import numpy as np
import pandas as pd  # type: ignore[import-untyped]


class ExportHelpers:
    """Export utility functions.

    Static methods for data export operations.
    """

    @staticmethod
    def quick_export_csv(app: Application) -> None:
        """Quick export cycle of interest data to CSV file.

        Args:
            app: Application instance

        """
        from PySide6.QtWidgets import QFileDialog  # type: ignore[import-untyped]

        try:
            # Get cursor positions
            start_time = app.main_window.full_timeline_graph.start_cursor.value()
            stop_time = app.main_window.full_timeline_graph.stop_cursor.value()

            # Check if there's data to export
            has_data = False
            for ch in app._idx_to_channel:
                if len(app.buffer_mgr.cycle_data[ch].time) > 0:
                    has_data = True
                    break

            if not has_data:
                from affilabs.widgets.message import show_message

                show_message("No cycle data to export", "Warning")
                return

            # Generate default filename
            from affilabs.utils.time_utils import for_filename

            timestamp = for_filename().replace(".", "_")
            default_filename = f"Cycle_Export_{timestamp}.csv"

            # Show save dialog
            file_path, _ = QFileDialog.getSaveFileName(
                app.main_window,
                "Export Cycle Data",
                default_filename,
                "CSV Files (*.csv);;All Files (*.*)",
            )

            if not file_path:
                return  # User cancelled

            # Collect cycle data for all channels
            export_data = {}
            for ch in app._idx_to_channel:
                cycle_time = app.buffer_mgr.cycle_data[ch].time
                delta_spr = app.buffer_mgr.cycle_data[ch].spr

                if len(cycle_time) > 0:
                    export_data[ch] = {
                        "time": cycle_time.copy(),
                        "spr": delta_spr.copy(),
                    }

            # Vectorized export using pandas DataFrame for better performance
            # Build DataFrame with time column from first available channel
            first_ch = list(export_data.keys())[0]
            df_data = {"Time (s)": export_data[first_ch]["time"]}

            # Add SPR columns for all channels
            for ch in app._idx_to_channel:
                if ch in export_data:
                    # Align all channels to same length (pandas handles this automatically)
                    df_data[f"Channel_{ch.upper()}_SPR (RU)"] = export_data[ch]["spr"]

            df = pd.DataFrame(df_data)

            # Write to CSV with metadata header
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                # Write metadata
                f.write("# AffiLabs Cycle Export\n")
                from affilabs.utils.time_utils import now_utc_iso

                f.write(f"# Export Date,{now_utc_iso()}\n")
                f.write(f"# Start Time (s),{start_time:.2f}\n")
                f.write(f"# Stop Time (s),{stop_time:.2f}\n")
                f.write(f"# Duration (s),{stop_time - start_time:.2f}\n")
                f.write("\n")

                # Write DataFrame (vectorized, much faster than manual loops)
                df.to_csv(f, index=False, float_format="%.4f")

            print(f"[OK] Cycle data exported to: {file_path}")
            from affilabs.widgets.message import show_message

            show_message(
                f"Cycle exported successfully!\n{Path(file_path).name}",
                "Information",
            )

        except Exception as e:
            print(f"Failed to export cycle CSV: {e}")
            from affilabs.widgets.message import show_message

            show_message(f"Export failed: {e}", "Error")

    @staticmethod
    def autosave_cycle_data(app: Application, start_time: float, stop_time: float) -> None:
        """Automatically save cycle data to session folder.

        Overwrites a single "current_cycle.csv" file instead of creating multiple timestamped files.
        This prevents file spam while still preserving the current cycle selection.

        Args:
            app: Application instance
            start_time: Cycle start time in seconds
            stop_time: Cycle stop time in seconds

        """
        try:
            # Create cycles subfolder in session directory
            if (
                not hasattr(app, "_session_cycles_dir")
                or app._session_cycles_dir is None
            ):
                if (
                    app.recording_mgr
                    and hasattr(app.recording_mgr, "current_session_dir")
                    and app.recording_mgr.current_session_dir is not None
                ):
                    session_dir = Path(app.recording_mgr.current_session_dir)
                    app._session_cycles_dir = session_dir / "cycles"
                else:
                    # Use data folder if no active session
                    from affilabs.utils.time_utils import now_utc

                    session_dir = Path("data") / "cycles" / now_utc().strftime("%Y%m%d")
                    app._session_cycles_dir = session_dir

                app._session_cycles_dir.mkdir(parents=True, exist_ok=True)

            # Use a single filename that gets overwritten (no timestamp spam)
            filename = "current_cycle.csv"
            filepath = app._session_cycles_dir / filename

            # Determine which channels have data
            active_channels = []
            for ch in app._idx_to_channel:
                if len(app.buffer_mgr.cycle_data[ch].time) > 0:
                    active_channels.append(ch)

            if not active_channels:
                return

            # Find maximum length across all channels (for padding)
            max_len = max(
                len(app.buffer_mgr.cycle_data[ch].time) for ch in active_channels
            )

            if max_len == 0:
                return

            # Vectorized export using pandas DataFrame
            # Build DataFrame with time and wavelength/SPR for each channel
            first_ch = active_channels[0]

            # Pad time array to max_len with NaN
            time_array = app.buffer_mgr.cycle_data[first_ch].time
            if len(time_array) < max_len:
                time_array = np.pad(
                    time_array,
                    (0, max_len - len(time_array)),
                    constant_values=np.nan,
                )

            df_data = {"Time (s)": time_array}

            for ch in active_channels:
                # Pad wavelength and SPR arrays to match max_len
                wave_array = app.buffer_mgr.cycle_data[ch].wavelength
                spr_array = app.buffer_mgr.cycle_data[ch].spr

                if len(wave_array) < max_len:
                    wave_array = np.pad(
                        wave_array,
                        (0, max_len - len(wave_array)),
                        constant_values=np.nan,
                    )
                if len(spr_array) < max_len:
                    spr_array = np.pad(
                        spr_array,
                        (0, max_len - len(spr_array)),
                        constant_values=np.nan,
                    )

                df_data[f"Ch {ch.upper()} Wavelength (nm)"] = wave_array
                df_data[f"Ch {ch.upper()} SPR (RU)"] = spr_array

            df = pd.DataFrame(df_data)

            # Write to CSV with metadata
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                # Write metadata
                f.write("# AffiLabs Cycle Autosave\n")
                from affilabs.utils.time_utils import now_utc_iso

                f.write(f"# Timestamp,{now_utc_iso()}\n")
                f.write(f"# Cycle Start,{start_time:.3f} s\n")
                f.write(f"# Cycle Stop,{stop_time:.3f} s\n")
                f.write(f"# Duration,{stop_time - start_time:.3f} s\n")
                f.write(f"# Filter Enabled,{app._filter_enabled!s}\n")
                if app._filter_enabled:
                    f.write(f"# Filter Strength,{app._filter_strength!s}\n")
                f.write(f"# Reference Subtraction,{app._ref_subtraction_enabled!s}\n")
                if app._ref_subtraction_enabled:
                    f.write(f"# Reference Channel,{app._ref_channel}\n")
                f.write("\n")

                # Write DataFrame (vectorized)
                df.to_csv(f, index=False, float_format="%.4f")

            # Save flag metadata to JSON
            metadata = {
                "timestamp": now_utc_iso(),
                "cycle_start": start_time,
                "cycle_stop": stop_time,
                "duration": stop_time - start_time,
                "cycle_type": app.sidebar.cycle_type_combo.currentText() if hasattr(app, 'sidebar') else "Unknown",
                "cycle_length": app.sidebar.cycle_length_combo.currentText() if hasattr(app, 'sidebar') else "Unknown",
                "note": app.sidebar.note_input.toPlainText() if hasattr(app, 'sidebar') else "",
                "units": app.sidebar.units_combo.currentText() if hasattr(app, 'sidebar') else "RU",
                "filter_enabled": app._filter_enabled if hasattr(app, '_filter_enabled') else False,
                "filter_strength": app._filter_strength if hasattr(app, '_filter_strength') and app._filter_enabled else None,
                "reference_subtraction": app._ref_subtraction_enabled if hasattr(app, '_ref_subtraction_enabled') else False,
                "reference_channel": app._ref_channel if hasattr(app, '_ref_channel') and app._ref_subtraction_enabled else None,
                "flags": [],
                "channel_offsets": {},
                "injection_time": None
            }

            # Extract flag data if it exists
            if hasattr(app, '_flag_markers') and app._flag_markers:
                for flag in app._flag_markers:
                    metadata["flags"].append({
                        "channel": flag["channel"],
                        "time": flag["time"],
                        "spr": flag["spr"],
                        "type": flag["type"]
                    })

                # Find injection time (first injection flag)
                injection_flags = [f for f in app._flag_markers if f["type"] == "injection"]
                if injection_flags:
                    metadata["injection_time"] = injection_flags[0]["time"]

            # Extract channel offsets if they exist
            if hasattr(app, '_channel_offsets'):
                metadata["channel_offsets"] = dict(app._channel_offsets)

            # Save JSON metadata file
            json_filepath = filepath.with_suffix('.json')
            import json
            with open(json_filepath, 'w', encoding='utf-8') as jf:
                json.dump(metadata, jf, indent=2)

            # Count flags by type for display
            flag_counts = {}
            for flag in metadata["flags"]:
                flag_type = flag["type"]
                flag_counts[flag_type] = flag_counts.get(flag_type, 0) + 1

            flag_summary = ", ".join(f"{t.capitalize()}:{c}" for t, c in flag_counts.items()) if flag_counts else "No flags"

            print(
                f"Cycle autosaved to {filename} ({len(active_channels)} channels, {len(df)} points, {flag_summary})",
            )

        except Exception as e:
            print(f"Cycle autosave failed: {e}")

    @staticmethod
    def export_requested(app: Application, config: dict) -> None:
        """Handle comprehensive export request from Export tab.

        Args:
            app: Application instance
            config: Export configuration dict with keys:
                - data_types: Dict of {raw, processed, cycles, summary} bools
                - channels: List of channel letters to export
                - format: 'excel', 'csv', 'json', or 'hdf5'
                - include_metadata: bool
                - include_events: bool
                - precision: int (decimal places)
                - timestamp_format: 'relative', 'absolute', or 'elapsed'
                - filename: str (base filename)
                - destination: str (directory path)
                - preset: str or None ('quick_csv', 'analysis', 'publication')

        """
        from PySide6.QtWidgets import QFileDialog

        try:
            print(f"Export requested with config: {config.get('preset', 'custom')}")

            # Check if there's data to export
            has_data = False
            for ch in app._idx_to_channel:
                if len(app.buffer_mgr.cycle_data[ch].time) > 0:
                    has_data = True
                    break

            if not has_data:
                from affilabs.widgets.message import show_message

                show_message(
                    "No cycle data available to export. Start acquisition and record some data first.",
                    msg_type="Warning",
                    title="No Data",
                )
                return

            # Determine filename and path
            filename = config.get("filename", "")
            if not filename:
                from affilabs.utils.time_utils import for_filename

                timestamp = for_filename().replace(".", "_")
                filename = f"AffiLabs_Export_{timestamp}"

            destination = config.get("destination", "")
            if not destination:
                destination = str(Path.home() / "Documents")

            # Add appropriate extension
            format_type = config.get("format", "excel")
            extension_map = {
                "excel": ".xlsx",
                "csv": ".csv",
                "json": ".json",
                "hdf5": ".h5",
            }
            extension = extension_map.get(format_type, ".xlsx")

            # Show save dialog
            default_path = str(Path(destination) / f"{filename}{extension}")
            file_filter = {
                "excel": "Excel Files (*.xlsx);;All Files (*.*)",
                "csv": "CSV Files (*.csv);;All Files (*.*)",
                "json": "JSON Files (*.json);;All Files (*.*)",
                "hdf5": "HDF5 Files (*.h5);;All Files (*.*)",
            }.get(format_type, "All Files (*.*)")

            file_path, _ = QFileDialog.getSaveFileName(
                app.main_window,
                "Export Data",
                default_path,
                file_filter,
            )

            if not file_path:
                print("Export cancelled by user")
                return

            # Collect data based on configuration
            channels = config.get("channels", ["a", "b", "c", "d"])
            data_types = config.get("data_types", {})
            precision = config.get("precision", 4)

            # Build export data structure
            export_data = {}

            for ch in channels:
                if ch not in app._idx_to_channel:
                    continue

                ch_data = {}

                # Raw data
                if data_types.get("raw", True):
                    cycle_time = app.buffer_mgr.cycle_data[ch].time
                    delta_spr = app.buffer_mgr.cycle_data[ch].spr
                    if len(cycle_time) > 0:
                        ch_data["raw"] = pd.DataFrame(
                            {
                                "Time (s)": cycle_time,
                                f"Channel_{ch.upper()}_SPR (RU)": delta_spr,
                            },
                        ).round(precision)

                # Processed data (if available)
                if data_types.get("processed", True):
                    # Use same data for now (filtering happens in display)
                    if len(app.buffer_mgr.cycle_data[ch].time) > 0:
                        ch_data["processed"] = ch_data.get("raw", pd.DataFrame()).copy()

                export_data[ch] = ch_data

            # Export using strategy pattern
            exporter = ExportHelpers._get_export_strategy(format_type)
            exporter.export(file_path, export_data, config)

            print(f"[OK] Data exported successfully to: {file_path}")
            from affilabs.widgets.message import show_message

            show_message(
                f"Data exported successfully to:\n{file_path}",
                msg_type="Information",
                title="Export Complete",
            )

        except Exception as e:
            print(f"Export failed: {e}")
            from affilabs.widgets.message import show_message

            show_message(
                f"Failed to export data:\n{e!s}",
                msg_type="Critical",
                title="Export Error",
            )

    @staticmethod
    def _get_export_strategy(format_type: str):
        """Factory method to get appropriate export strategy.

        Args:
            format_type: Export format ('excel', 'csv', 'json', 'hdf5')

        Returns:
            ExportStrategy instance for the specified format

        """
        from affilabs.utils.export_strategies import get_export_strategy

        return get_export_strategy(format_type)

    @staticmethod
    def quick_export_image(app: Application) -> None:
        """Quick export cycle of interest graph as image with metadata.

        Args:
            app: Application instance

        """
        import datetime as dt

        from PySide6.QtCore import QRectF, Qt
        from PySide6.QtGui import QFont, QImage, QPainter, QPen
        from PySide6.QtWidgets import QFileDialog

        try:
            # Check if there's data to export
            has_data = False
            for ch in app._idx_to_channel:
                if len(app.buffer_mgr.cycle_data[ch].time) > 0:
                    has_data = True
                    break

            if not has_data:
                from affilabs.widgets.message import show_message

                show_message("No cycle data to export", "Warning")
                return

            # Generate default filename
            timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"Cycle_Graph_{timestamp}.png"

            # Show save dialog
            file_path, _ = QFileDialog.getSaveFileName(
                app.main_window,
                "Export Graph Image",
                default_filename,
                "PNG Images (*.png);;JPEG Images (*.jpg);;All Files (*.*)",
            )

            if not file_path:
                return  # User cancelled

            # Get graph widget
            graph_widget = app.main_window.cycle_of_interest_graph

            # Export graph to image
            exporter = graph_widget.getPlotItem().scene().views()[0]

            # Get cursor positions for metadata
            start_time = app.main_window.full_timeline_graph.start_cursor.value()
            stop_time = app.main_window.full_timeline_graph.stop_cursor.value()

            # Create image with extra space for metadata
            graph_rect = exporter.viewport().rect()
            metadata_height = 100
            total_width = graph_rect.width()
            total_height = graph_rect.height() + metadata_height

            image = QImage(total_width, total_height, QImage.Format_ARGB32)
            image.fill(Qt.white)

            # Render graph to image
            painter = QPainter(image)
            exporter.render(
                painter,
                target=QRectF(0, 0, total_width, graph_rect.height()),
            )

            # Add metadata text below graph
            painter.setFont(QFont("Arial", 9))
            painter.setPen(QPen(Qt.black))

            y_offset = graph_rect.height() + 15
            line_height = 15

            # Metadata lines
            metadata_lines = [
                f"AffiLabs Cycle of Interest - Exported: {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"Time Range: {start_time:.2f}s - {stop_time:.2f}s  |  Duration: {stop_time - start_time:.2f}s",
                "Channels: A (Red), B (Green), C (Blue), D (Purple)  |  Unit: Response Units (RU)",
            ]

            for i, line in enumerate(metadata_lines):
                painter.drawText(10, y_offset + (i * line_height), line)

            painter.end()

            # Save image
            image.save(file_path)

            print(f"[OK] Graph image exported to: {file_path}")
            from affilabs.widgets.message import show_message

            show_message(
                f"Graph exported successfully!\n{Path(file_path).name}",
                "Information",
            )

        except Exception as e:
            print(f"Failed to export graph image: {e}")
            from affilabs.widgets.message import show_message

            show_message(f"Export failed: {e}", "Error")
