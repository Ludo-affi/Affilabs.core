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

        This is the GATEWAY to saving recorded data to file.
        Shows confirmation dialog with filename/location before saving.

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
        from PySide6.QtWidgets import QFileDialog, QMessageBox

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
                    "No data available to export. Start recording some data first.",
                    msg_type="Warning",
                    title="No Data",
                )
                return

            # Determine target path and format
            format_type = config.get("format", "excel")
            extension_map = {
                "excel": ".xlsx",
                "csv": ".csv",
                "json": ".json",
                "hdf5": ".h5",
            }
            extension = extension_map.get(format_type, ".xlsx")

            # Unify with active recording file when possible: if a recording file exists and we're exporting Excel,
            # write into that same workbook instead of creating a separate file.
            full_path = None
            if (
                hasattr(app, "recording_mgr")
                and app.recording_mgr is not None
                and getattr(app.recording_mgr, "current_file", None)
                and str(app.recording_mgr.current_file).lower().endswith(".xlsx")
                and format_type == "excel"
            ):
                full_path = Path(str(app.recording_mgr.current_file))
            else:
                # Fallback to configured destination + filename
                filename = config.get("filename", "")
                if not filename:
                    from affilabs.utils.time_utils import for_filename
                    timestamp = for_filename().replace(".", "_")
                    filename = f"AffiLabs_data_{timestamp}"

                destination = config.get("destination", "")
                if not destination:
                    destination = str(Path.home() / "Documents" / "Affilabs Data")

                # Ensure extension is on filename
                if not filename.endswith(extension):
                    filename += extension

                full_path = Path(destination) / filename

            # Show confirmation dialog BEFORE saving
            msg = QMessageBox(app.main_window)
            msg.setIcon(QMessageBox.Question)
            msg.setWindowTitle("Export Data")
            # Show destination based on unified path
            msg.setText(
                f"Ready to save recorded data.\n\nFile: {full_path.name}\nLocation: {str(full_path.parent)}"
            )
            msg.setInformativeText("Click SAVE to export data, or CANCEL to adjust the filename/location.")

            save_btn = msg.addButton("SAVE", QMessageBox.AcceptRole)
            cancel_btn = msg.addButton("Cancel", QMessageBox.RejectRole)
            msg.setDefaultButton(save_btn)

            msg.exec()

            if msg.clickedButton() == cancel_btn:
                print("Export cancelled by user")
                return

            # User clicked SAVE - proceed with export
            channels = config.get("channels", ["a", "b", "c", "d"])
            data_types = config.get("data_types", {})
            precision = config.get("precision", 4)

            # Build raw data in LONG format (each channel has its own timestamp)
            # This is critical because channels are measured in SERIES not PARALLEL
            raw_data_rows = []

            for ch in channels:
                if ch not in app._idx_to_channel:
                    continue

                # Get channel-specific time and wavelength arrays
                cycle_time = app.buffer_mgr.cycle_data[ch].time
                wavelength = app.buffer_mgr.cycle_data[ch].wavelength

                if len(cycle_time) > 0:
                    # Create one row per measurement (long format)
                    for t, w in zip(cycle_time, wavelength):
                        raw_data_rows.append({
                            'time': round(t, precision),
                            'channel': ch,
                            'value': round(w, precision)
                        })

            # Create DataFrame from long format data
            if raw_data_rows:
                df_raw = pd.DataFrame(raw_data_rows)

                # Get cycle metadata from recording manager if available
                cycles_data = []
                if hasattr(app, 'recording_mgr') and app.recording_mgr.data_collector:
                    cycles_data = app.recording_mgr.data_collector.cycles

                # Ensure destination directory exists
                full_path.parent.mkdir(parents=True, exist_ok=True)

                # Export using format-specific logic
                if format_type == "excel":
                    # If writing to an existing recording workbook, append/replace only the Channels XY sheet;
                    # otherwise, create a full new workbook with all sheets.
                    if (
                        hasattr(app, "recording_mgr")
                        and app.recording_mgr is not None
                        and getattr(app.recording_mgr, "current_file", None)
                        and str(app.recording_mgr.current_file).lower().endswith(".xlsx")
                        and Path(str(app.recording_mgr.current_file)) == full_path
                    ):
                        try:
                            # Write or replace 'Channels XY' sheet in existing workbook
                            # Build Channels XY DataFrame
                            all_channels = channels
                            max_len = 0
                            for ch in all_channels:
                                if ch in app._idx_to_channel:
                                    max_len = max(max_len, len(app.buffer_mgr.cycle_data[ch].time))

                            if max_len > 0:
                                sheet_data: dict[str, np.ndarray] = {}
                                for ch in all_channels:
                                    if ch not in app._idx_to_channel:
                                        sheet_data[f"Time_{ch.upper()}"] = np.full((max_len,), np.nan)
                                        sheet_data[f"SPR_{ch.upper()}"] = np.full((max_len,), np.nan)
                                        continue

                                    ch_time = app.buffer_mgr.cycle_data[ch].time
                                    ch_spr = app.buffer_mgr.cycle_data[ch].spr

                                    if len(ch_time) < max_len:
                                        ch_time = np.pad(ch_time, (0, max_len - len(ch_time)), constant_values=np.nan)
                                    if len(ch_spr) < max_len:
                                        ch_spr = np.pad(ch_spr, (0, max_len - len(ch_spr)), constant_values=np.nan)

                                    sheet_data[f"Time_{ch.upper()}"] = ch_time
                                    sheet_data[f"SPR_{ch.upper()}"] = ch_spr

                                df_xy = pd.DataFrame(sheet_data)

                                with pd.ExcelWriter(
                                    str(full_path),
                                    engine='openpyxl',
                                    mode='a',
                                    if_sheet_exists='replace'
                                ) as writer:
                                    df_xy.to_excel(writer, sheet_name='Channels XY', index=False)
                        except Exception as e:
                            print(f"Warning: could not update 'Channels XY' in recording file: {e}")
                    else:
                        with pd.ExcelWriter(str(full_path), engine='openpyxl') as writer:
                            # Sheet 1: Raw Data
                            df_raw.to_excel(writer, sheet_name='Raw Data', index=False)

                            # Sheet 2: Cycles (if available)
                            if cycles_data:
                                df_cycles = pd.DataFrame(cycles_data)
                                df_cycles.to_excel(writer, sheet_name='Cycles', index=False)

                            # Sheet 3: Flags (if available from recording manager)
                            if hasattr(app, 'recording_mgr') and app.recording_mgr.data_collector.flags:
                                df_flags = pd.DataFrame(app.recording_mgr.data_collector.flags)
                                df_flags.to_excel(writer, sheet_name='Flags', index=False)

                            # Sheet 4: Events (if available from recording manager)
                            if hasattr(app, 'recording_mgr') and app.recording_mgr.data_collector.events:
                                df_events = pd.DataFrame(app.recording_mgr.data_collector.events)
                                df_events.to_excel(writer, sheet_name='Events', index=False)

                            # Sheet 5: Metadata (if available from recording manager)
                            if hasattr(app, 'recording_mgr') and app.recording_mgr.data_collector.metadata:
                                df_meta = pd.DataFrame([app.recording_mgr.data_collector.metadata])
                                df_meta.to_excel(writer, sheet_name='Metadata', index=False)

                            # Sheet 6: Per-Channel XY (time and SPR per channel)
                            try:
                                all_channels = channels
                                max_len = 0
                                for ch in all_channels:
                                    if ch in app._idx_to_channel:
                                        max_len = max(max_len, len(app.buffer_mgr.cycle_data[ch].time))

                                if max_len > 0:
                                    sheet_data: dict[str, np.ndarray] = {}
                                    for ch in all_channels:
                                        if ch not in app._idx_to_channel:
                                            sheet_data[f"Time_{ch.upper()}"] = np.full((max_len,), np.nan)
                                            sheet_data[f"SPR_{ch.upper()}"] = np.full((max_len,), np.nan)
                                            continue

                                        ch_time = app.buffer_mgr.cycle_data[ch].time
                                        ch_spr = app.buffer_mgr.cycle_data[ch].spr

                                        if len(ch_time) < max_len:
                                            ch_time = np.pad(ch_time, (0, max_len - len(ch_time)), constant_values=np.nan)
                                        if len(ch_spr) < max_len:
                                            ch_spr = np.pad(ch_spr, (0, max_len - len(ch_spr)), constant_values=np.nan)

                                        sheet_data[f"Time_{ch.upper()}"] = ch_time
                                        sheet_data[f"SPR_{ch.upper()}"] = ch_spr

                                    df_xy = pd.DataFrame(sheet_data)
                                    df_xy.to_excel(writer, sheet_name='Channels XY', index=False)
                            except Exception as e:
                                # Non-fatal: continue export even if XY sheet fails
                                print(f"Warning: could not create 'Channels XY' sheet: {e}")
                elif format_type == "csv":
                    df_raw.to_csv(str(full_path), index=False)
                elif format_type == "json":
                    df_raw.to_json(str(full_path), orient='records', indent=2)
                else:
                    # Fallback to CSV
                    df_raw.to_csv(str(full_path), index=False)

            print(f"[OK] Data exported successfully to: {full_path}")
            from affilabs.widgets.message import show_message

            show_message(
                f"Data exported successfully to:\n{full_path}",
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
