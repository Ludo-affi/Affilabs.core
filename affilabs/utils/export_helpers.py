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

import time

import numpy as np
import pandas as pd  # type: ignore[import-untyped]


class ExportHelpers:
    """Export utility functions.

    Static methods for data export operations.
    """

    @staticmethod
    def deduplicate_cycles_dataframe(df_cycles: pd.DataFrame) -> pd.DataFrame:
        """Deduplicate cycles DataFrame by cycle_id or cycle_num.
        
        This is a shared utility used during export to ensure no duplicate cycles
        are written to output files. Should complement DataCollector.add_cycle() 
        which prevents duplicates during accumulation.
        
        Args:
            df_cycles: DataFrame with cycle data
            
        Returns:
            Deduplicated DataFrame with duplicate rows removed
        """
        if df_cycles.empty:
            return df_cycles
            
        original_count = len(df_cycles)
        
        # Try cycle_id first (primary key)
        if 'cycle_id' in df_cycles.columns:
            df_cycles = df_cycles.drop_duplicates(subset=['cycle_id'], keep='first')
        # Fall back to cycle_num
        elif 'cycle_num' in df_cycles.columns:
            df_cycles = df_cycles.drop_duplicates(subset=['cycle_num'], keep='first')
        
        removed_count = original_count - len(df_cycles)
        if removed_count > 0:
            from affilabs.utils.logger import logger
            logger.warning(
                f"Removed {removed_count} duplicate cycle rows during export "
                f"({original_count} → {len(df_cycles)})"
            )
        
        return df_cycles

    @staticmethod
    def build_channels_xy_dataframe(buffer_mgr, channels: list[str] | None = None) -> pd.DataFrame:
        """Build Channels XY DataFrame for Excel export.
        
        Creates wide-format DataFrame with Time_A, SPR_A, Time_B, SPR_B columns.
        All arrays padded to same length with NaN for alignment.
        
        Uses timeline_data (full experiment) NOT cycle_data (cursor window) so the
        exported sheet always contains the complete recording, not just whatever
        happened to be visible in the "Cycle of Interest" panel at save time.
        
        SPR (delta from baseline) is computed using baseline_wavelengths if available,
        falling back to the first valid point in each channel's timeline.
        
        This is a shared utility to eliminate duplication across export paths.
        Used by: recording_manager, export_helpers (2 places)
        
        Args:
            buffer_mgr: DataBufferManager instance with timeline_data attribute
            channels: List of channel letters (default: ['a', 'b', 'c', 'd'])
            
        Returns:
            DataFrame with Channels XY data, or empty DataFrame if no data
        """
        from affilabs.app_config import WAVELENGTH_TO_RU_CONVERSION

        if channels is None:
            channels = ['a', 'b', 'c', 'd']
        
        # Use timeline_data (full experiment) — cycle_data only holds the cursor
        # window which is at most the last cycle visible in the bottom graph.
        source = buffer_mgr.timeline_data

        # Find max length across all channels
        max_len = 0
        for ch in channels:
            if ch in source and hasattr(source[ch], 'time'):
                max_len = max(max_len, len(source[ch].time))
        
        if max_len == 0:
            return pd.DataFrame()  # Empty DataFrame - no channel data
        
        # Build sheet data with Time_X and SPR_X columns for each channel
        sheet_data = {}
        for ch in channels:
            ch_upper = ch.upper()
            
            buf = source.get(ch) if isinstance(source, dict) else getattr(source, ch, None)
            if buf is not None and hasattr(buf, 'time') and len(buf.time) > 0:
                ch_time = np.array(buf.time)
                ch_wavelength = np.array(buf.wavelength)

                # Compute delta SPR from baseline
                # Prefer calibrated baseline; fall back to first valid wavelength in timeline
                baseline = None
                if hasattr(buffer_mgr, 'baseline_wavelengths'):
                    baseline = buffer_mgr.baseline_wavelengths.get(ch)
                if baseline is None:
                    for wl in ch_wavelength:
                        if 560.0 <= wl <= 720.0:
                            baseline = float(wl)
                            break
                if baseline is None and len(ch_wavelength) > 0:
                    baseline = float(ch_wavelength[0])
                baseline = baseline or 0.0

                ch_spr = (ch_wavelength - baseline) * WAVELENGTH_TO_RU_CONVERSION

                # Pad to max length if needed (ensures all columns same length)
                if len(ch_time) < max_len:
                    ch_time = np.pad(ch_time, (0, max_len - len(ch_time)), constant_values=np.nan)
                    ch_spr = np.pad(ch_spr, (0, max_len - len(ch_spr)), constant_values=np.nan)
            else:
                # Channel has no data - fill entire column with NaN
                ch_time = np.full((max_len,), np.nan)
                ch_spr = np.full((max_len,), np.nan)
            
            sheet_data[f"Time_{ch_upper}"] = ch_time
            sheet_data[f"SPR_{ch_upper}"] = ch_spr
        
        return pd.DataFrame(sheet_data)

    @staticmethod
    def build_channels_xy_from_wide_dataframe(df_wide: pd.DataFrame, channels: list[str] | None = None) -> pd.DataFrame:
        """Build Channels XY DataFrame from wide-format DataFrame.
        
        Converts wide-format DataFrame (with columns A, B, C, D representing values)
        into per-channel format with Time_X and X columns for each channel.
        Used by edits_tab exports to reuse per-channel padding logic.
        
        Args:
            df_wide: Wide-format DataFrame with 'Time' column and channel columns (A, B, C, D)
            channels: List of channel letters (default: ['A', 'B', 'C', 'D'])
            
        Returns:
            DataFrame with Time_A, A, Time_B, B, Time_C, C, Time_D, D columns
        """
        if channels is None:
            channels = ['A', 'B', 'C', 'D']
        
        if df_wide.empty or 'Time' not in df_wide.columns:
            return pd.DataFrame()  # Empty if no data or no Time column
        
        # Build per-channel dict with time and value columns
        per_channel_dict = {}
        max_len = 0
        
        for ch in channels:
            if ch in df_wide.columns:
                # Extract non-null times and values for this channel
                valid_mask = df_wide[ch].notna()
                times = df_wide.loc[valid_mask, 'Time'].values
                values = df_wide.loc[valid_mask, ch].values
                per_channel_dict[f'Time_{ch}'] = list(times)
                per_channel_dict[ch] = list(values)
                max_len = max(max_len, len(times))
            else:
                # Channel not in data
                per_channel_dict[f'Time_{ch}'] = []
                per_channel_dict[ch] = []
        
        # Pad all arrays to same max length with None (which pandas converts to NaN)
        for key in per_channel_dict:
            while len(per_channel_dict[key]) < max_len:
                per_channel_dict[key].append(None)
        
        return pd.DataFrame(per_channel_dict)

    @staticmethod
    def quick_export_csv(app: Application) -> None:
        """Quick export cycle of interest data to CSV file.

        Args:
            app: Application instance

        """
        from PySide6.QtWidgets import QFileDialog  # type: ignore[import-untyped]

        try:
            # Get cursor positions (display coords — used for CSV metadata header only)
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

            # Build user-specific default path
            default_dir = Path.home() / "Documents" / "Affilabs Data"
            current_user = app._get_current_user() if hasattr(app, '_get_current_user') else ""
            if current_user:
                default_dir = default_dir / current_user / "SPR_data"
            default_dir.mkdir(parents=True, exist_ok=True)

            # Show save dialog
            file_path, _ = QFileDialog.getSaveFileName(
                app.main_window,
                "Export Cycle Data",
                str(default_dir / default_filename),
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
                f.write(f"# Start Time (display s),{start_time:.2f}\n")
                f.write(f"# Stop Time (display s),{stop_time:.2f}\n")
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

            # Get current user for metadata (used in both CSV header and JSON)
            current_user = "Unknown"
            if hasattr(app, '_get_current_user'):
                current_user = app._get_current_user() or "Unknown"
            elif hasattr(app, 'user_profile_manager') and app.user_profile_manager:
                current_user = app.user_profile_manager.get_current_user() or "Unknown"

            # Write to CSV with metadata
            from affilabs.utils.time_utils import now_utc_iso

            with open(filepath, "w", newline="", encoding="utf-8") as f:
                # Write metadata
                f.write("# AffiLabs Cycle Autosave\n")
                f.write(f"# Timestamp,{now_utc_iso()}\n")
                f.write(f"# Operator,{current_user}\n")
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

            metadata = {
                "timestamp": now_utc_iso(),
                "operator": current_user,
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

            # Extract flag data from FlagManager (unified flag system)
            # NOTE: app._flag_markers (legacy dict list) is never populated; use flag_mgr instead.
            if hasattr(app, 'flag_mgr') and app.flag_mgr is not None:
                try:
                    for flag in app.flag_mgr.get_live_flags():
                        metadata["flags"].append({
                            "channel": flag.channel,
                            "time": flag.time,
                            "spr": flag.spr,
                            "type": flag.flag_type,
                        })
                    # Find injection time (first injection flag)
                    injection_flags = [f for f in metadata["flags"] if f["type"] == "injection"]
                    if injection_flags:
                        metadata["injection_time"] = injection_flags[0]["time"]
                except Exception as _fe:
                    logger.debug(f"Could not extract flags for autosave metadata: {_fe}")

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
        from PySide6.QtWidgets import QMessageBox

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

                # Always resolve user-specific directory dynamically (same as Edits tab)
                # Ignores stale export_dest_input value — always uses current user
                if hasattr(app, 'recording_mgr') and hasattr(app.recording_mgr, 'get_user_output_directory'):
                    destination = str(app.recording_mgr.get_user_output_directory())
                else:
                    current_user = app._get_current_user() if hasattr(app, '_get_current_user') else ""
                    if current_user:
                        destination = str(Path.home() / "Documents" / "Affilabs Data" / current_user / "SPR_data")
                    else:
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
                    # otherwise, create a full new workbook with all sheets via ExcelExporter
                    if (
                        hasattr(app, "recording_mgr")
                        and app.recording_mgr is not None
                        and getattr(app.recording_mgr, "current_file", None)
                        and str(app.recording_mgr.current_file).lower().endswith(".xlsx")
                        and Path(str(app.recording_mgr.current_file)) == full_path
                    ):
                        try:
                            # Write or replace 'Channels XY' sheet in existing workbook (append mode)
                            df_xy = ExportHelpers.build_channels_xy_dataframe(app.buffer_mgr, channels)
                            
                            if not df_xy.empty:
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
                        # Use ExcelExporter service for complete workbook creation
                        from affilabs.services.excel_exporter import ExcelExporter
                        excel_exporter = ExcelExporter()
                        
                        # Gather all data from recording manager if available
                        raw_data_rows_for_export = []
                        cycles_data_for_export = []
                        flags_data = []
                        events_data = []
                        metadata_data = {}
                        recording_start_time = time.time()
                        channels_xy_df = None
                        
                        if hasattr(app, 'recording_mgr') and app.recording_mgr is not None:
                            collector = app.recording_mgr.data_collector
                            raw_data_rows_for_export = collector.raw_data_rows
                            cycles_data_for_export = collector.cycles
                            flags_data = collector.flags
                            events_data = collector.events
                            metadata_data = collector.metadata
                            recording_start_time = collector.recording_start_time
                        else:
                            # Fallback: build raw data from buffer_mgr
                            raw_data_rows_for_export = raw_data_rows
                        
                        # Build Channels XY sheet if buffer_mgr available
                        try:
                            if app.buffer_mgr is not None:
                                channels_xy_df = ExportHelpers.build_channels_xy_dataframe(
                                    app.buffer_mgr,
                                    channels=channels
                                )
                        except Exception as e:
                            print(f"Warning: Could not build Channels XY sheet: {e}")
                        
                        # Get timeline stream if recording_mgr available
                        _tl_stream = None
                        try:
                            if hasattr(app, 'recording_mgr') and app.recording_mgr is not None:
                                _tl_stream = app.recording_mgr.get_timeline_stream()
                        except Exception:
                            pass

                        excel_exporter.export_to_excel(
                            filepath=full_path,
                            raw_data_rows=raw_data_rows_for_export,
                            cycles=cycles_data_for_export,
                            flags=flags_data,
                            events=events_data,
                            analysis_results=[],
                            metadata=metadata_data,
                            recording_start_time=recording_start_time,
                            alignment_data=None,
                            channels_xy_dataframe=channels_xy_df,
                            timeline_stream=_tl_stream,
                        )
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
