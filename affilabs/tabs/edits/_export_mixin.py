"""Export Mixin for EditsTab.

Contains all export-related methods extracted from EditsTab:
- _export_selection, _export_raw_data_long_format, _export_raw_data_direct, _export_raw_data
- _export_barchart_image, _export_graph_image
- _create_export_sidebar, _export_sidebar_button, _toggle_export_sidebar, _update_export_sidebar_stats
- _save_cycles_as_method, _copy_table_to_clipboard, _export_for_external_software
- _export_table_data, _write_csv
"""

from pathlib import Path

import pyqtgraph as pg
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QWidget, QScrollArea, QApplication,
)
from PySide6.QtCore import Qt

from affilabs.utils.logger import logger


class ExportMixin:
    """Mixin providing all export functionality for EditsTab."""

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _build_canonical_cycles_df(self, cycle_indices=None):
        """Return a DataFrame in the canonical 'Cycles' sheet format.

        Column names match what live export (excel_exporter.py) writes and what
        the Edits loader (_edits_cycle_mixin.py) expects, so files round-trip
        cleanly.  Pass cycle_indices to restrict to specific rows; None = all.
        """
        import pandas as pd
        cycles = getattr(self.main_window, '_loaded_cycles_data', None)
        if not cycles:
            return pd.DataFrame()

        rows = (
            [cycles[i].copy() for i in cycle_indices if i < len(cycles)]
            if cycle_indices is not None
            else [c.copy() for c in cycles]
        )

        for row in rows:
            if isinstance(row.get('concentrations'), dict):
                row['concentrations'] = str(row['concentrations'])

        # Enrich rows with quality score + note from _cycle_details_data
        details_cache = getattr(self, '_cycle_details_data', {})
        all_cycles = getattr(self.main_window, '_loaded_cycles_data', []) or []
        for row in rows:
            row_cycle_id = row.get('cycle_id', '')
            # Find the row_idx that corresponds to this cycle_id
            for row_idx, det in details_cache.items():
                if det.get('cycle_id') == row_cycle_id:
                    row['quality_score'] = det.get('quality_score', '')
                    row['quality_note'] = det.get('quality_note', '')
                    break

        df = pd.DataFrame(rows)
        preferred = [
            'cycle_id', 'cycle_num', 'type', 'name',
            'start_time_sensorgram', 'end_time_sensorgram', 'duration_minutes',
            'concentration_value', 'concentration_units', 'concentrations',
            'note', 'delta_spr', 'delta_spr_by_channel', 'flags', 'timestamp',
            'quality_score', 'quality_note',
        ]
        ec = [c for c in preferred if c in df.columns]
        oc = [c for c in df.columns if c not in preferred and c != 'shift']
        return df[ec + oc]

    def _build_metadata_sheet(self, extra: dict | None = None) -> "pd.DataFrame":
        """Assemble the canonical Metadata sheet DataFrame for an Edits export.

        Pulls data from three sources:
        - ``data_collector.metadata`` — instrument/session fields set during recording
        - ``ExperimentIndex`` entry matched by source file path — ELN fields (rating,
          tags, notes, kanban_status) edited in the Notes tab
        - ``extra`` dict — caller-supplied override/additional keys

        Returns a DataFrame with columns ``key`` and ``value``, using the same
        sectioned key-value layout written by the live exporter so the Metadata
        sheet is identical whether the file comes from a fresh recording or from
        an Edits re-save.
        """
        import pandas as pd
        from datetime import datetime

        meta: dict = {}

        # --- 1. Recorded metadata (instrument/session) -----------------------
        try:
            dc = self.main_window.app.recording_mgr.data_collector
            meta.update(dc.metadata or {})
        except Exception:
            pass

        # --- 2. Loaded metadata (round-tripped from source file) -------------
        try:
            loaded = getattr(self.main_window, '_loaded_metadata', None) or {}
            for k, v in loaded.items():
                if k not in meta:
                    meta[k] = v
        except Exception:
            pass

        # --- 3. ELN fields from ExperimentIndex (Notes tab) ------------------
        eln: dict = {}
        try:
            from affilabs.services.experiment_index import ExperimentIndex
            from pathlib import Path
            source = getattr(self.main_window, '_edits_source_file', None)
            if source:
                src_path = Path(source)
                idx = ExperimentIndex()
                # Match by file path — entries store relative paths so try stem match too
                for entry in idx.all_entries():
                    entry_file = Path(entry.get("file", ""))
                    if (entry_file == src_path
                            or entry_file.name == src_path.name
                            or entry_file.stem == src_path.stem):
                        eln = entry
                        break
        except Exception:
            pass

        # --- 4. Caller overrides ---------------------------------------------
        if extra:
            meta.update(extra)

        # --- Build sectioned rows --------------------------------------------
        user = eln.get("user") or meta.get("operator") or meta.get("User") or "Unknown"
        tags_raw = eln.get("tags") or []
        tags_str = ", ".join(tags_raw) if isinstance(tags_raw, list) else str(tags_raw)

        rows = [
            # Experiment
            ("section",           "Experiment"),
            ("experiment_id",     eln.get("id") or meta.get("experiment_id", "")),
            ("recording_start",   meta.get("recording_start", "")),
            ("recording_end",     datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            ("duration",          f"{float(eln['duration_min']):.1f} min" if eln.get("duration_min") else ""),
            ("cycle_count",       str(eln.get("cycle_count") or len(getattr(getattr(self.main_window, 'app', None), '_loaded_cycles_data', None) or []))),
            ("method_name",       meta.get("method_name", "")),
            ("description",       eln.get("description") or meta.get("description", "")),
            # Instrument
            ("section",           "Instrument"),
            ("device_id",         meta.get("device_id") or meta.get("detector_serial", "")),
            ("hardware_model",    eln.get("hardware_model") or meta.get("hardware_model", "")),
            ("sensor_type",       meta.get("sensor_type", "")),
            ("firmware_version",  meta.get("firmware_version", "")),
            ("software_version",  meta.get("software_version", "")),
            # Sample
            ("section",           "Sample"),
            ("chip_serial",       eln.get("chip_serial") or meta.get("chip_serial") or meta.get("detector_serial", "")),
            ("ligand",            meta.get("ligand", "")),
            ("analyte",           meta.get("analyte", "")),
            ("buffer",            meta.get("buffer", "")),
            ("temperature_c",     meta.get("temperature_c", "")),
            # Operator
            ("section",           "Operator"),
            ("operator",          user),
            ("lab",               meta.get("lab", "")),
            ("project",           meta.get("project", "")),
            # ELN
            ("section",           "ELN"),
            ("rating",            str(eln.get("rating") or "")),
            ("tags",              tags_str),
            ("kanban_status",     eln.get("kanban_status", "")),
            ("notes",             eln.get("notes", "")),
            # Channel shifts
            ("section",           "Channel Shifts"),
            ("channel_a_shift_s", str(meta.get("channel_a_time_shift", meta.get("channel_a_shift", "")))),
            ("channel_b_shift_s", str(meta.get("channel_b_time_shift", meta.get("channel_b_shift", "")))),
            ("channel_c_shift_s", str(meta.get("channel_c_time_shift", meta.get("channel_c_shift", "")))),
            ("channel_d_shift_s", str(meta.get("channel_d_time_shift", meta.get("channel_d_shift", "")))),
        ]

        # Any extra keys in meta not already covered
        known = {r[0] for r in rows} | {"section"}
        leftover = [(k, str(v)) for k, v in meta.items() if k not in known]
        if leftover:
            rows.append(("section", "Other"))
            rows.extend(leftover)

        return pd.DataFrame(rows, columns=["key", "value"])

    def _get_source_xy_sheet(self):
        """Return the Per-Channel Format DataFrame from the source file, or None.

        Edits never modifies the raw XY signal data — if we have the source file
        on disk we pass its Per-Channel Format sheet through unchanged rather than
        reconstructing it from raw_data_rows (which would re-apply the nm→RU
        conversion and lose the original values).
        """
        import pandas as pd
        source = getattr(self.main_window, '_edits_source_file', None)
        if not source or not isinstance(source, str):
            return None
        try:
            from pathlib import Path
            if not Path(source).exists():
                return None
            sheets = pd.read_excel(source, sheet_name=['Per-Channel Format'], engine='openpyxl')
            return sheets.get('Per-Channel Format')
        except Exception:
            return None

    def _apply_version_management(
        self,
        file_path: str,
        *,
        action: str,
        cycle_indices: list[int] | None = None,
        fields_changed: str = "",
        notes: str = "",
    ) -> None:
        """Apply ExcelVersionManager to ``file_path`` after a save.

        Only runs when the destination IS the source file (in-place overwrite).
        Silently skips if the version manager is unavailable.

        Parameters
        ----------
        file_path : str
            Path that was just written.
        action : str
            Human-readable description of the save operation.
        cycle_indices : list[int] | None
            Row indices of cycles that were exported/modified.
        fields_changed : str
            Comma-separated column names that changed (optional).
        notes : str
            Extra context (smoothing level, alignment applied, etc.).
        """
        try:
            from affilabs.services.excel_version_manager import ExcelVersionManager

            # Resolve user
            user = "Unknown"
            try:
                user = self.main_window.app.user_profile_manager.get_current_user() or "Unknown"
            except Exception:
                pass

            # Build cycles_affected string
            cycles_affected = ""
            if cycle_indices is not None:
                cycles_data = getattr(self.main_window, '_loaded_cycles_data', [])
                ids = []
                for i in cycle_indices:
                    if i < len(cycles_data):
                        c = cycles_data[i]
                        ids.append(str(c.get('cycle_id', c.get('cycle_num', i + 1))))
                cycles_affected = ", ".join(ids)

            ExcelVersionManager.apply(
                file_path,
                action=action,
                user=user,
                cycles_affected=cycles_affected,
                fields_changed=fields_changed,
                notes=notes,
            )
        except Exception:
            pass  # Version management is non-critical — never block a save

    # ── Core Export Methods ──────────────────────────────────────────────────

    def _export_package(self):
        """Export Package: single workbook with all data + embedded graph images.

        Captures the visible Sensorgram and ΔSPR bar chart as PNG images,
        then delegates to ``_export_post_edit_analysis_with_charts()`` which
        creates one ``.xlsx`` file containing data sheets, interactive Excel
        charts **and** embedded graph images — all in a single workbook.
        """
        from affilabs.utils.logger import logger
        if hasattr(self.main_window, 'stage_bar'):
            try:
                _chip = self.main_window.transport_bar.step_chip
                # Only advance to "export" if the user has already reviewed data (edit=index 4)
                if _chip._completed_idx >= 4:
                    self.main_window.stage_bar.advance_to("export")
            except Exception:
                self.main_window.stage_bar.advance_to("export")

        # ── Capture graph images as PNG bytes ────────────────────────────
        graph_images: dict[str, bytes] = {}

        try:
            exporter = pg.exporters.ImageExporter(self.edits_primary_graph.plotItem)
            exporter.parameters()['width'] = 2400
            from PySide6.QtCore import QBuffer, QIODevice
            buf = QBuffer()
            buf.open(QIODevice.OpenModeFlag.ReadWrite)
            exporter.export(buf)
            graph_images['Sensorgram'] = bytes(buf.data())
            buf.close()
            logger.debug("Captured sensorgram image for package export")
        except Exception as e:
            logger.warning(f"Export package — could not capture sensorgram: {e}")

        try:
            exporter = pg.exporters.ImageExporter(self.delta_spr_barchart.plotItem)
            exporter.parameters()['width'] = 1200
            from PySide6.QtCore import QBuffer, QIODevice
            buf = QBuffer()
            buf.open(QIODevice.OpenModeFlag.ReadWrite)
            exporter.export(buf)
            graph_images['ΔSPR Chart'] = bytes(buf.data())
            buf.close()
            logger.debug("Captured ΔSPR chart image for package export")
        except Exception as e:
            logger.warning(f"Export package — could not capture ΔSPR chart: {e}")

        # ── Create single workbook with embedded images ──────────────────
        self._export_post_edit_analysis_with_charts(graph_images=graph_images or None)

    def _export_selection(self):
        """Export data from Edits tab to Excel.

        Two modes:
        1. If cycles exist and are selected: Export combined sensorgram with cycles
        2. If no cycles (live data): Export raw data directly
        """
        from affilabs.utils.logger import logger
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        import pandas as pd
        from datetime import datetime

        try:
            # Check if we have raw data available (either from Send to Edits or loaded file)
            raw_data = None

            # Option 1: Data from Send to Edits (stored in main_window._edits_raw_data)
            if hasattr(self.main_window, '_edits_raw_data') and self.main_window._edits_raw_data is not None:
                raw_data = self.main_window._edits_raw_data

            # Option 2: Data loaded from file (stored in recording_mgr.data_collector.raw_data_rows)
            elif hasattr(self.main_window, 'app') and hasattr(self.main_window.app, 'recording_mgr'):
                if hasattr(self.main_window.app.recording_mgr, 'data_collector'):
                    if hasattr(self.main_window.app.recording_mgr.data_collector, 'raw_data_rows'):
                        raw_rows = self.main_window.app.recording_mgr.data_collector.raw_data_rows
                        if raw_rows and len(raw_rows) > 0:
                            # Keep raw data in original format (don't pivot)
                            # Just pass the raw_rows list directly for long format export
                            self._export_raw_data_long_format(raw_rows)
                            return

            # If we have raw data, export it directly
            if raw_data is not None and len(raw_data) > 0:
                self._export_raw_data_direct(raw_data)
                return

            # Otherwise, export selected cycles (original behavior)
            # Get selected cycles
            selected_rows = sorted(set(item.row() for item in self.cycle_data_table.selectedItems()))

            if not selected_rows:
                QMessageBox.information(
                    self.main_window,
                    "No Selection",
                    "Please select one or more cycles to export."
                )
                return

            # Get filename from user
            file_path = self._get_save_path("Export Combined Sensorgram")

            if not file_path:
                return  # User cancelled

            logger.info(f"[EXPORT] Exporting combined sensorgram to: {file_path}")

            # Collect data from all selected cycles with alignment settings
            export_data = []
            metadata = []

            for row in selected_rows:
                if row >= len(self.main_window._loaded_cycles_data):
                    continue

                cycle = self.main_window._loaded_cycles_data[row]

                # Get alignment settings
                channel_filter = 'All'
                time_shift = 0.0
                if hasattr(self.main_window, '_cycle_alignment') and row in self.main_window._cycle_alignment:
                    channel_filter = self.main_window._cycle_alignment[row]['channel']
                    time_shift = self.main_window._cycle_alignment[row]['shift']

                # Get cycle time range
                start_time = cycle.get('start_time_sensorgram', cycle.get('sensorgram_time'))
                end_time = cycle.get('end_time_sensorgram')

                if start_time is None:
                    continue

                if end_time is None:
                    duration_min = cycle.get('duration_minutes', cycle.get('length_minutes', 5))
                    end_time = start_time + (duration_min * 60) if duration_min else start_time + 300

                # Extract delta SPR values for each channel
                delta_by_ch = self._parse_delta_spr(cycle)

                # Get individual channel delta values (fallback to delta_ch1-4 if needed)
                delta_a = delta_by_ch.get('A', cycle.get('delta_ch1', ''))
                delta_b = delta_by_ch.get('B', cycle.get('delta_ch2', ''))
                delta_c = delta_by_ch.get('C', cycle.get('delta_ch3', ''))
                delta_d = delta_by_ch.get('D', cycle.get('delta_ch4', ''))

                # Record metadata with separate delta SPR columns
                metadata.append({
                    'Cycle_Index': row,
                    'Cycle_Type': cycle.get('type', 'Unknown'),
                    'Channel_Filter': channel_filter,
                    'Time_Shift_s': time_shift,
                    'Start_Time_s': start_time,
                    'End_Time_s': end_time,
                    'Duration_min': cycle.get('duration_minutes', ''),
                    'Concentration': cycle.get('concentration_value', ''),
                    'Units': cycle.get('concentration_units', ''),
                    'Delta_A': delta_a if delta_a != '' else '',
                    'Delta_B': delta_b if delta_b != '' else '',
                    'Delta_C': delta_c if delta_c != '' else '',
                    'Delta_D': delta_d if delta_d != '' else '',
                })

                # Get raw data
                raw_data = self.main_window.app.recording_mgr.data_collector.raw_data_rows

                # Filter and process data
                WAVELENGTH_TO_RU = 355.0
                baseline_wavelengths = {}

                for row_data in raw_data:
                    time = row_data.get('elapsed', row_data.get('time', 0))
                    if start_time <= time <= end_time:
                        relative_time = time - start_time + time_shift

                        # Handle both data formats
                        if 'channel' in row_data and 'value' in row_data:
                            ch = row_data.get('channel')
                            value = row_data.get('value')

                            # Apply channel filter
                            if channel_filter != 'All' and ch != channel_filter.lower():
                                continue

                            if ch in self.CHANNELS_LOWER and value is not None:
                                # Calculate baseline (first value for this channel)
                                if ch not in baseline_wavelengths:
                                    baseline_wavelengths[ch] = value

                                # Convert to RU
                                delta_wavelength = value - baseline_wavelengths[ch]
                                ru_value = delta_wavelength * WAVELENGTH_TO_RU

                                export_data.append({
                                    'Time_s': relative_time,
                                    'Channel': ch.upper(),
                                    'Wavelength_nm': value,
                                    'Response_RU': ru_value,
                                    'Cycle_Index': row,
                                    'Cycle_Type': cycle.get('type', 'Unknown')
                                })
                        else:
                            # Wide format
                            for ch in self.CHANNELS_LOWER:
                                if channel_filter != 'All' and ch != channel_filter.lower():
                                    continue

                                wavelength = row_data.get(f'channel_{ch}', row_data.get(f'wavelength_{ch}'))
                                if wavelength is not None:
                                    if ch not in baseline_wavelengths:
                                        baseline_wavelengths[ch] = wavelength

                                    delta_wavelength = wavelength - baseline_wavelengths[ch]
                                    ru_value = delta_wavelength * WAVELENGTH_TO_RU

                                    export_data.append({
                                        'Time_s': relative_time,
                                        'Channel': ch.upper(),
                                        'Wavelength_nm': wavelength,
                                        'Response_RU': ru_value,
                                        'Cycle_Index': row,
                                        'Cycle_Type': cycle.get('type', 'Unknown')
                                    })

                logger.info(f"[EXPORT] Cycle {row}: Extracted {len([d for d in export_data if d['Cycle_Index'] == row])} data points")

            # Create Excel file with multiple sheets
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                # Sheet 1: Combined data in long format (original format)
                df_data_long = pd.DataFrame(export_data)
                df_data_long = df_data_long.sort_values(['Time_s', 'Channel'])
                df_data_long.to_excel(writer, sheet_name='Combined Data (Long)', index=False)

                # Sheet 2: Per-channel format (Time_A, A, Time_B, B, Time_C, C, Time_D, D)
                # Convert long format to wide per-channel format using shared utility
                from affilabs.utils.export_helpers import ExportHelpers

                # Build wide DataFrame from long format
                df_wide = df_data_long.pivot_table(
                    index='Time_s',
                    columns='Channel',
                    values='Response_RU',
                    aggfunc='first'
                ).reset_index()
                df_wide.rename(columns={'Time_s': 'Time'}, inplace=True)

                # Use shared utility to build per-channel format
                df_per_channel = ExportHelpers.build_channels_xy_from_wide_dataframe(df_wide, channels=self.CHANNELS)
                if not df_per_channel.empty:
                    # Reorder columns: Time_A, SPR_A, Time_B, SPR_B, ...
                    column_order = [col for ch in self.CHANNELS for col in [f'Time_{ch}', f'SPR_{ch}'] if col in df_per_channel.columns]
                    df_per_channel = df_per_channel[column_order]
                    df_per_channel.to_excel(writer, sheet_name='Per-Channel Format', index=False)

                # Sheet 3: Metadata
                df_meta = pd.DataFrame(metadata)
                df_meta.to_excel(writer, sheet_name='Cycle Metadata', index=False)

                # Sheet 3b: Canonical "Cycles" sheet — matches live export format so this
                # file can be reloaded into Edits without column-name translation.
                df_canonical = self._build_canonical_cycles_df(cycle_indices=selected_rows)
                if not df_canonical.empty:
                    df_canonical.to_excel(writer, sheet_name='Cycles', index=False)

                # Sheet 4: Alignment settings (for re-loading)
                if self._cycle_alignment:
                    alignment_rows = []
                    for cycle_idx, settings in self._cycle_alignment.items():
                        if cycle_idx in selected_rows:
                            alignment_rows.append({
                                'Cycle_Index': cycle_idx,
                                'Channel_Filter': settings.get('channel', 'All'),
                                'Time_Shift_s': settings.get('shift', 0.0)
                            })
                    if alignment_rows:
                        df_alignment = pd.DataFrame(alignment_rows)
                        df_alignment.to_excel(writer, sheet_name='Alignment', index=False)

                # Sheet 5: Export info
                self._build_metadata_sheet(extra={
                    'export_type': 'selection',
                    'total_cycles': str(len(selected_rows)),
                    'total_data_points': str(len(export_data)),
                }).to_excel(writer, sheet_name='Metadata', index=False)

            logger.info(f"✓ Exported {len(export_data)} data points from {len(selected_rows)} cycles")

            self._apply_version_management(
                file_path,
                action=f"Export selection ({len(selected_rows)} cycle(s))",
                cycle_indices=list(selected_rows),
                fields_changed="Combined Data (Long), Per-Channel Format, Cycles",
                notes=f"Alignment applied; {len(export_data)} data points",
            )

            QMessageBox.information(
                self.main_window,
                "Export Complete",
                f"Combined sensorgram exported successfully!\n\n"
                f"File: {file_path}\n"
                f"Cycles: {len(selected_rows)}\n"
                f"Data points: {len(export_data)}"
            )

        except Exception as e:
            logger.exception(f"Error exporting selection: {e}")
            QMessageBox.critical(
                self.main_window,
                "Export Error",
                f"Failed to export combined sensorgram:\n{str(e)}"
            )

    def _export_raw_data_long_format(self, raw_rows):
        """
        Export raw data in LONG format (Time, Channel, Value) and also create per-channel format.
        This avoids the sparse wide-format with lots of NaN values.
        """
        import pandas as pd
        from datetime import datetime
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from affilabs.utils.logger import logger
        from affilabs.utils.time_utils import filename_timestamp

        # Ensure experiment folder exists
        exp_folder = self._ensure_experiment_folder()

        # Get default save location in Raw_Data subfolder
        if exp_folder:
            raw_data_folder = self.main_window.app.experiment_folder_mgr.get_subfolder_path(
                exp_folder, "Raw_Data"
            )
            default_filename = f"Raw_{filename_timestamp()}.xlsx"
            default_path = str(raw_data_folder / default_filename)
        else:
            # Fallback if no experiment folder
            default_filename = f"Raw_{filename_timestamp()}.xlsx"
            default_path = default_filename

        # Ask user for save location (defaults to experiment folder)
        file_path = self._get_save_path("Save Raw Data")

        if not file_path:
            return

        # Convert raw_rows to long format DataFrame
        rows_list = []
        for row in raw_rows:
            time_key = 'elapsed' if 'elapsed' in row else 'time'
            rows_list.append({
                'Time': row[time_key],
                'Channel': row['channel'].upper(),
                'Value': row['value']
            })

        df_long = pd.DataFrame(rows_list)

        # Also create wide format for per-channel extraction
        df_wide = df_long.pivot_table(
            index='Time',
            columns='Channel',
            values='Value',
            aggfunc='first'
        ).reset_index()

        # Get cycle table data if available (match Edits table columns)
        cycles_table = []
        if hasattr(self.main_window, '_loaded_cycles_data') and self.main_window._loaded_cycles_data:
            for idx, cycle in enumerate(self.main_window._loaded_cycles_data):
                # Extract individual delta SPR values for separate columns
                delta_by_ch = self._parse_delta_spr(cycle)

                # Get individual channel delta values (fallback to delta_ch1-4 if needed)
                delta_a = delta_by_ch.get('A', cycle.get('delta_ch1', ''))
                delta_b = delta_by_ch.get('B', cycle.get('delta_ch2', ''))
                delta_c = delta_by_ch.get('C', cycle.get('delta_ch3', ''))
                delta_d = delta_by_ch.get('D', cycle.get('delta_ch4', ''))

                # Build Flags string (icon + time)
                flags_str = self._format_flags_display(cycle)

                cycles_table.append({
                    'Cycle #': cycle.get('cycle_number', idx + 1),
                    'Type': cycle.get('type', 'Unknown'),
                    'Duration (min)': cycle.get('duration_minutes', ''),
                    'Start Time (s)': cycle.get('start_time', ''),
                    'Concentration': cycle.get('concentration_value', ''),
                    'Units': cycle.get('concentration_units', ''),
                    'Delta_A': delta_a if delta_a != '' else '',
                    'Delta_B': delta_b if delta_b != '' else '',
                    'Delta_C': delta_c if delta_c != '' else '',
                    'Delta_D': delta_d if delta_d != '' else '',
                    'Flags': flags_str,
                    'Notes': cycle.get('note', cycle.get('notes', '')),
                    'Cycle ID': cycle.get('cycle_id', ''),
                })

        # Export to Excel with multiple sheets
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            # Sheet 1: Raw data in LONG format (Time, Channel, Value - no NaNs!)
            df_long.to_excel(writer, sheet_name='Raw Data', index=False)

            # Sheet 2: Per-channel format — pass through source file unchanged if available,
            # otherwise reconstruct from raw_data_rows.
            df_source_xy = self._get_source_xy_sheet()
            if df_source_xy is not None:
                df_source_xy.to_excel(writer, sheet_name='Per-Channel Format', index=False)
            else:
                from affilabs.utils.export_helpers import ExportHelpers
                df_per_channel = ExportHelpers.build_channels_xy_from_wide_dataframe(df_wide, channels=self.CHANNELS)
                if not df_per_channel.empty:
                    df_per_channel.to_excel(writer, sheet_name='Per-Channel Format', index=False)

            # Sheet 3: Cycle Table (display columns — human-readable)
            if cycles_table:
                df_cycles = pd.DataFrame(cycles_table)
                df_cycles.to_excel(writer, sheet_name='Cycle Table', index=False)

            # Sheet 3b: Canonical "Cycles" sheet — reload-compatible format
            df_canonical = self._build_canonical_cycles_df()
            if not df_canonical.empty:
                df_canonical.to_excel(writer, sheet_name='Cycles', index=False)

            # Sheet 4: Export info
            self._build_metadata_sheet(extra={
                'export_type': 'raw_data_long',
                'total_data_points': str(len(df_long)),
                'channels': ', '.join(df_long['Channel'].unique()),
            }).to_excel(writer, sheet_name='Metadata', index=False)

        logger.info(f"[EXPORT] Exported {len(df_long)} rows to: {file_path}")

        self._apply_version_management(
            file_path,
            action="Export raw data (long format)",
            fields_changed="Raw Data, Per-Channel Format, Cycles",
            notes=f"{len(df_long)} data points",
        )

        # Register file in experiment metadata (if using experiment folder)
        if exp_folder and Path(file_path).is_relative_to(exp_folder):
            self.main_window.app.experiment_folder_mgr.register_file(
                exp_folder,
                Path(file_path),
                "raw_data",
                f"Raw sensor data export with {len(df_long)} data points"
            )
            logger.debug(f"Registered raw data file in experiment metadata")

        max_len = len(df_long)
        metadata_text = f"Exported to:\n{file_path}\n\n"
        metadata_text += f"Raw Data: {len(df_long)} rows (long format)\n"
        metadata_text += f"Per-Channel Format: {max_len} rows\n"
        metadata_text += f"Channels: {', '.join(df_long['Channel'].unique())}"

        QMessageBox.information(self.main_window, "Export Complete", metadata_text)

    def _export_raw_data_direct(self, df_raw):
        """Export raw data DataFrame directly to Excel in per-channel format.

        Args:
            df_raw: DataFrame with columns Time, A, B, C, D
        """
        from affilabs.utils.logger import logger
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        import pandas as pd
        from datetime import datetime

        try:
            if df_raw is None or len(df_raw) == 0:
                QMessageBox.warning(
                    self.main_window,
                    "No Data",
                    "No data available to export."
                )
                return

            # Get filename from user with user-specific default folder
            default_name = f"Edits_Data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            default_dir = self._get_user_export_dir()
            file_path, _ = QFileDialog.getSaveFileName(
                self.main_window,
                "Export Data",
                str(default_dir / default_name),
                "Excel Files (*.xlsx);;All Files (*)"
            )

            if not file_path:
                return  # User cancelled

            logger.info(f"[EXPORT] Exporting data to: {file_path}")

            # Create Excel file with multiple sheets
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                # Sheet 1: Raw data (Time, A, B, C, D format)
                df_raw.to_excel(writer, sheet_name='Raw Data', index=False)

                # Sheet 2: Per-channel format — pass through source file unchanged if available.
                df_source_xy = self._get_source_xy_sheet()
                if df_source_xy is not None:
                    df_source_xy.to_excel(writer, sheet_name='Per-Channel Format', index=False)
                else:
                    per_channel_dict = {}
                    for ch in self.CHANNELS:
                        if ch in df_raw.columns:
                            valid_mask = df_raw[ch].notna()
                            times = df_raw.loc[valid_mask, 'Time'].values
                            values = df_raw.loc[valid_mask, ch].values
                            per_channel_dict[f'Time_{ch}'] = list(times)
                            per_channel_dict[f'SPR_{ch}'] = list(values)
                        else:
                            per_channel_dict[f'Time_{ch}'] = []
                            per_channel_dict[f'SPR_{ch}'] = []
                    max_len = max((len(per_channel_dict[f'Time_{ch}']) for ch in self.CHANNELS), default=0)
                    for ch in self.CHANNELS:
                        cur = len(per_channel_dict[f'Time_{ch}'])
                        if cur < max_len:
                            per_channel_dict[f'Time_{ch}'].extend([None] * (max_len - cur))
                            per_channel_dict[f'SPR_{ch}'].extend([None] * (max_len - cur))
                    column_order = [col for ch in self.CHANNELS for col in [f'Time_{ch}', f'SPR_{ch}']]
                    pd.DataFrame(per_channel_dict)[column_order].to_excel(
                        writer, sheet_name='Per-Channel Format', index=False
                    )

                # Sheet 3: Cycle Table
                cycles_table = []
                if hasattr(self.main_window, '_loaded_cycles_data') and self.main_window._loaded_cycles_data:
                    for idx, cycle in enumerate(self.main_window._loaded_cycles_data):
                        # Extract individual delta SPR values for separate columns
                        delta_by_ch = self._parse_delta_spr(cycle)

                        # Get individual channel delta values (fallback to delta_ch1-4 if needed)
                        delta_a = delta_by_ch.get('A', cycle.get('delta_ch1', ''))
                        delta_b = delta_by_ch.get('B', cycle.get('delta_ch2', ''))
                        delta_c = delta_by_ch.get('C', cycle.get('delta_ch3', ''))
                        delta_d = delta_by_ch.get('D', cycle.get('delta_ch4', ''))

                        cycles_table.append({
                            'Cycle #': cycle.get('cycle_number', idx + 1),
                            'Type': cycle.get('type', 'Unknown'),
                            'Duration (min)': cycle.get('duration_minutes', ''),
                            'Concentration': cycle.get('concentration_value', ''),
                            'Units': cycle.get('concentration_units', ''),
                            'Delta_A': delta_a if delta_a != '' else '',
                            'Delta_B': delta_b if delta_b != '' else '',
                            'Delta_C': delta_c if delta_c != '' else '',
                            'Delta_D': delta_d if delta_d != '' else '',
                            'Notes': cycle.get('notes', '')
                        })

                if cycles_table:
                    df_cycles = pd.DataFrame(cycles_table)
                    df_cycles.to_excel(writer, sheet_name='Cycle Table', index=False)

                # Sheet 3b: Canonical "Cycles" sheet — reload-compatible format
                df_canonical = self._build_canonical_cycles_df()
                if not df_canonical.empty:
                    df_canonical.to_excel(writer, sheet_name='Cycles', index=False)

                # Sheet 4: Metadata
                self._build_metadata_sheet(extra={
                    'export_type': 'raw_data_direct',
                    'total_data_points': str(len(df_raw)),
                }).to_excel(writer, sheet_name='Metadata', index=False)

            logger.info(f"✓ Exported {len(df_raw)} data points")

            self._apply_version_management(
                file_path,
                action="Export data (direct)",
                fields_changed="Raw Data, Per-Channel Format, Cycles",
                notes=f"{len(df_raw)} data points",
            )

            QMessageBox.information(
                self.main_window,
                "Export Complete",
                f"Data exported successfully!\n\n"
                f"File: {file_path}\n"
                f"Data points: {len(df_raw)}\n"
                f"Sheets: Raw Data + Per-Channel Format"
            )

        except Exception as e:
            logger.exception(f"Error exporting data: {e}")
            QMessageBox.critical(
                self.main_window,
                "Export Error",
                f"Failed to export data:\n{str(e)}"
            )

    def _export_raw_data(self):
        """Export raw data (from Send to Edits) to Excel in per-channel format."""
        from affilabs.utils.logger import logger
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        import pandas as pd
        from datetime import datetime

        try:
            # Get raw data DataFrame
            df_raw = self.main_window._edits_raw_data

            if df_raw is None or len(df_raw) == 0:
                QMessageBox.warning(
                    self.main_window,
                    "No Data",
                    "No data available to export."
                )
                return

            # Get filename from user with user-specific default folder
            default_name = f"Live_Data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            default_dir = self._get_user_export_dir()
            file_path, _ = QFileDialog.getSaveFileName(
                self.main_window,
                "Export Live Data",
                str(default_dir / default_name),
                "Excel Files (*.xlsx);;All Files (*)"
            )

            if not file_path:
                return  # User cancelled

            logger.info(f"[EXPORT] Exporting raw data to: {file_path}")

            # Create Excel file with multiple sheets
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                # Sheet 1: Raw data (Time, A, B, C, D format)
                df_raw.to_excel(writer, sheet_name='Raw Data', index=False)

                # Sheet 2: Per-channel format — pass through source file unchanged if available.
                df_source_xy = self._get_source_xy_sheet()
                if df_source_xy is not None:
                    df_source_xy.to_excel(writer, sheet_name='Per-Channel Format', index=False)
                else:
                    per_channel_dict = {}
                    for ch in self.CHANNELS:
                        if ch in df_raw.columns:
                            valid_mask = df_raw[ch].notna()
                            times = df_raw.loc[valid_mask, 'Time'].values
                            values = df_raw.loc[valid_mask, ch].values
                            per_channel_dict[f'Time_{ch}'] = list(times)
                            per_channel_dict[f'SPR_{ch}'] = list(values)
                        else:
                            per_channel_dict[f'Time_{ch}'] = []
                            per_channel_dict[f'SPR_{ch}'] = []
                    max_len = max((len(per_channel_dict[f'Time_{ch}']) for ch in self.CHANNELS), default=0)
                    for ch in self.CHANNELS:
                        cur = len(per_channel_dict[f'Time_{ch}'])
                        if cur < max_len:
                            per_channel_dict[f'Time_{ch}'].extend([None] * (max_len - cur))
                            per_channel_dict[f'SPR_{ch}'].extend([None] * (max_len - cur))
                    column_order = [col for ch in self.CHANNELS for col in [f'Time_{ch}', f'SPR_{ch}']]
                    pd.DataFrame(per_channel_dict)[column_order].to_excel(
                        writer, sheet_name='Per-Channel Format', index=False
                    )

                # Sheet 3: Metadata
                self._build_metadata_sheet(extra={
                    'export_type': 'raw_data',
                    'total_data_points': str(len(df_raw)),
                }).to_excel(writer, sheet_name='Metadata', index=False)

            logger.info(f"✓ Exported {len(df_raw)} data points")

            self._apply_version_management(
                file_path,
                action="Export raw data",
                fields_changed="Raw Data, Per-Channel Format, Cycles",
                notes=f"{len(df_raw)} data points",
            )

            QMessageBox.information(
                self.main_window,
                "Export Complete",
                f"Data exported successfully!\n\n"
                f"File: {file_path}\n"
                f"Data points: {len(df_raw)}\n"
                f"Format: Raw Data + Per-Channel sheets"
            )

        except Exception as e:
            logger.exception(f"Error exporting raw data: {e}")
            QMessageBox.critical(
                self.main_window,
                "Export Error",
                f"Failed to export data:\n{str(e)}"
            )

    # ── Graph/Image Export ───────────────────────────────────────────────────

    def _export_barchart_image(self):
        """Export the delta SPR bar chart as an image."""
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from datetime import datetime

        # Open file dialog
        default_name = f"delta_spr_barchart_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        file_path, _ = QFileDialog.getSaveFileName(
            self.main_window,
            "Export Bar Chart",
            default_name,
            "PNG Image (*.png);;JPEG Image (*.jpg);;SVG Image (*.svg);;All Files (*.*)"
        )

        if not file_path:
            return  # User cancelled

        try:
            # Use pyqtgraph's export functionality
            exporter = pg.exporters.ImageExporter(self.delta_spr_barchart.plotItem)

            # Set resolution for better quality
            exporter.parameters()['width'] = 1200

            exporter.export(file_path)

            QMessageBox.information(
                self.main_window,
                "Export Successful",
                f"Bar chart exported to:\n{file_path}"
            )
        except Exception as e:
            QMessageBox.critical(
                self.main_window,
                "Export Failed",
                f"Failed to export bar chart:\n{str(e)}"
            )

    def _export_graph_image(self):
        """Export the active cycle graph as an image."""
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from datetime import datetime

        # Open file dialog
        default_name = f"sensorgram_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        file_path, _ = QFileDialog.getSaveFileName(
            self.main_window,
            "Export Sensorgram",
            default_name,
            "PNG Image (*.png);;JPEG Image (*.jpg);;SVG Image (*.svg);;All Files (*.*)"
        )

        if not file_path:
            return  # User cancelled

        try:
            # Use pyqtgraph's export functionality
            exporter = pg.exporters.ImageExporter(self.edits_primary_graph.plotItem)

            # Set resolution for better quality
            exporter.parameters()['width'] = 2400

            exporter.export(file_path)

            QMessageBox.information(
                self.main_window,
                "Export Successful",
                f"Sensorgram exported to:\n{file_path}"
            )
        except Exception as e:
            QMessageBox.critical(
                self.main_window,
                "Export Failed",
                f"Failed to export sensorgram:\n{str(e)}"
            )

    # ── Export Sidebar ───────────────────────────────────────────────────────

    def _create_export_sidebar(self):
        """Create the collapsible export sidebar panel for the Edit tab."""
        sidebar = QFrame()
        sidebar.setFixedWidth(280)
        sidebar.setStyleSheet("""
            QFrame#ExportSidebar {
                background: #FFFFFF;
                border-right: 1px solid #E5E5EA;
                border-radius: 0;
            }
        """)
        sidebar.setObjectName("ExportSidebar")

        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: transparent; width: 6px; margin: 0;
            }
            QScrollBar::handle:vertical {
                background: rgba(0,0,0,0.15); border-radius: 3px; min-height: 30px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        content = QWidget()
        content.setStyleSheet("background: #FFFFFF;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # ── Header ──
        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        header_icon = QLabel("📤")
        header_icon.setStyleSheet("font-size: 18px; background: transparent;")
        header_row.addWidget(header_icon)
        header_title = QLabel("EXPORT")
        header_title.setStyleSheet(
            "font-size: 14px; font-weight: 700; color: #1D1D1F; letter-spacing: 1px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "background: transparent;"
        )
        header_row.addWidget(header_title)
        header_row.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #86868B; border: none; "
            "font-size: 14px; font-weight: bold; border-radius: 12px; }"
            "QPushButton:hover { background: #F5F5F7; color: #1D1D1F; }"
        )
        close_btn.clicked.connect(self._toggle_export_sidebar)
        header_row.addWidget(close_btn)
        layout.addLayout(header_row)

        # Divider
        div1 = QFrame()
        div1.setFrameShape(QFrame.Shape.HLine)
        div1.setStyleSheet("border: none; background: #E5E5EA; max-height: 1px;")
        layout.addWidget(div1)

        # ── Export Analysis ──
        export_analysis_btn = self._export_sidebar_button(
            "💾", "Export Analysis",
            "Save cycle table to Excel (.xlsx) or CSV"
        )
        export_analysis_btn.clicked.connect(self._export_table_data)
        layout.addWidget(export_analysis_btn)

        # ── Export Analysis + Charts ──
        export_charts_btn = self._export_sidebar_button(
            "📊", "Export with Charts",
            "Complete analysis workbook with interactive Excel charts"
        )
        export_charts_btn.clicked.connect(self._export_post_edit_analysis_with_charts)
        layout.addWidget(export_charts_btn)

        # ── Save Cycles as Method ──
        save_method_btn = self._export_sidebar_button(
            "📋", "Save as Method",
            "Convert cycles to reusable method file (.json)"
        )
        save_method_btn.clicked.connect(self._save_cycles_as_method)
        layout.addWidget(save_method_btn)

        # Divider
        div2 = QFrame()
        div2.setFrameShape(QFrame.Shape.HLine)
        div2.setStyleSheet("border: none; background: #E5E5EA; max-height: 1px;")
        layout.addWidget(div2)

        # ── Export Sensorgram ──
        export_sensorgram_btn = self._export_sidebar_button(
            "📊", "Export Sensorgram",
            "Save active cycle graph as PNG image"
        )
        export_sensorgram_btn.clicked.connect(self._export_graph_image)
        layout.addWidget(export_sensorgram_btn)

        # ── Export ΔSPR Chart ──
        export_dspr_btn = self._export_sidebar_button(
            "📈", "Export ΔSPR Chart",
            "Save bar chart as PNG image"
        )
        export_dspr_btn.clicked.connect(self._export_barchart_image)
        layout.addWidget(export_dspr_btn)

        # Divider
        div3 = QFrame()
        div3.setFrameShape(QFrame.Shape.HLine)
        div3.setStyleSheet("border: none; background: #E5E5EA; max-height: 1px;")
        layout.addWidget(div3)

        # ── Copy to Clipboard ──
        copy_btn = self._export_sidebar_button(
            "📋", "Copy to Clipboard",
            "Copy selected cycles as tab-separated text"
        )
        copy_btn.clicked.connect(self._copy_table_to_clipboard)
        layout.addWidget(copy_btn)

        # ── External Software ──
        external_btn = self._export_sidebar_button(
            "🔗", "External Software",
            "Export concentration vs. ΔSPR table (CSV) for Prism / Origin. "
            "For TraceDrawer, use the raw recording export on the main tab."
        )
        external_btn.clicked.connect(self._export_for_external_software)
        layout.addWidget(external_btn)

        # Spacer
        layout.addSpacing(8)

        # ── Info / Stats Panel ──
        stats_frame = QFrame()
        stats_frame.setStyleSheet("""
            QFrame {
                background: rgba(0, 0, 0, 0.03);
                border-radius: 8px;
            }
        """)
        stats_layout = QVBoxLayout(stats_frame)
        stats_layout.setContentsMargins(12, 8, 12, 8)
        stats_layout.setSpacing(6)

        stats_title = QLabel("Summary")
        stats_title.setStyleSheet(
            "font-size: 12px; font-weight: 600; color: #1D1D1F; "
            "background: transparent;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        stats_layout.addWidget(stats_title)

        self.export_stats_cycles = QLabel("Cycles: 0")
        self.export_stats_cycles.setStyleSheet(
            "font-size: 12px; color: #86868B; background: transparent;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        stats_layout.addWidget(self.export_stats_cycles)

        self.export_stats_selected = QLabel("Selected: 0")
        self.export_stats_selected.setStyleSheet(
            "font-size: 12px; color: #86868B; background: transparent;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        stats_layout.addWidget(self.export_stats_selected)

        self.export_stats_channels = QLabel("Channels: A, B, C, D")
        self.export_stats_channels.setStyleSheet(
            "font-size: 12px; color: #86868B; background: transparent;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        stats_layout.addWidget(self.export_stats_channels)

        self.export_stats_duration = QLabel("Duration: —")
        self.export_stats_duration.setStyleSheet(
            "font-size: 12px; color: #86868B; background: transparent;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        stats_layout.addWidget(self.export_stats_duration)

        layout.addWidget(stats_frame)

        layout.addStretch()

        scroll.setWidget(content)

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.addWidget(scroll)

        return sidebar

    def _export_sidebar_button(self, icon_text, label_text, tooltip_text):
        """Create a styled export sidebar action button.

        Args:
            icon_text: Emoji icon string
            label_text: Button label
            tooltip_text: Tooltip description

        Returns:
            QPushButton with consistent styling
        """
        btn = QPushButton(f"  {icon_text}  {label_text}")
        btn.setFixedHeight(36)
        btn.setToolTip(tooltip_text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                background: white;
                color: #1D1D1F;
                border: 1px solid rgba(0, 0, 0, 0.1);
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
                padding: 8px 16px;
                text-align: left;
                font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;
            }
            QPushButton:hover {
                background: rgba(0, 0, 0, 0.06);
            }
            QPushButton:pressed {
                background: rgba(0, 0, 0, 0.1);
            }
        """)
        return btn

    def _toggle_export_sidebar(self):
        """Toggle the export sidebar visibility."""
        is_visible = self.export_sidebar.isVisible()
        self.export_sidebar.setVisible(not is_visible)

        # Sync toggle button checked state
        if hasattr(self, 'export_toggle_btn'):
            self.export_toggle_btn.setChecked(not is_visible)

        # Update stats when showing
        if not is_visible:
            self._update_export_sidebar_stats()

    def _update_export_sidebar_stats(self):
        """Update the export sidebar summary statistics."""
        if not hasattr(self, 'export_stats_cycles'):
            return

        # Total visible cycles
        total = 0
        for row in range(self.cycle_data_table.rowCount()):
            if not self.cycle_data_table.isRowHidden(row):
                total += 1

        selected_rows = self.cycle_data_table.selectionModel().selectedRows()
        selected = len(selected_rows)

        self.export_stats_cycles.setText(f"Cycles: {total}")
        self.export_stats_selected.setText(f"Selected: {selected}")

        # Channels (always 4 for now)
        self.export_stats_channels.setText("Channels: A, B, C, D")

        # Duration estimate from first/last visible cycle
        first_time = None
        last_time = None
        for row in range(self.cycle_data_table.rowCount()):
            if self.cycle_data_table.isRowHidden(row):
                continue
            time_item = self.cycle_data_table.item(row, 2)
            if time_item and time_item.text().strip():
                time_text = time_item.text().strip()
                if first_time is None:
                    first_time = time_text
                last_time = time_text

        if first_time and last_time:
            self.export_stats_duration.setText(f"Time: {first_time} → {last_time}")
        else:
            self.export_stats_duration.setText("Duration: —")

    # ── Save as Method / Clipboard / External ───────────────────────────────

    def _save_cycles_as_method(self):
        """Convert visible cycle table rows into a reusable method JSON file."""
        from PySide6.QtWidgets import QFileDialog, QMessageBox, QInputDialog
        from datetime import datetime
        import json

        # Collect visible rows from the cycle table
        cycle_dicts = []
        for row in range(self.cycle_data_table.rowCount()):
            if self.cycle_data_table.isRowHidden(row):
                continue

            # Extract data from table columns (5-column table: Export/Type/Time/Conc/ΔSPR)
            type_item = self.cycle_data_table.item(row, 1)
            time_item = self.cycle_data_table.item(row, 2)
            conc_item = self.cycle_data_table.item(row, 3)

            # Flags and notes come from _cycle_details_data, not the table
            cycle_details = getattr(self, '_cycle_details_data', {}).get(row, {})

            # Parse cycle type from display text (e.g., '● BL 1' → 'Baseline')
            raw_type = type_item.text().strip() if type_item else "Custom"
            full_type = type_item.toolTip() if type_item and type_item.toolTip() else raw_type

            # Map abbreviations back to full type names
            type_map = {
                'BL': 'Baseline', 'IM': 'Immobilization', 'WS': 'Wash',
                'CN': 'Concentration', 'RG': 'Regeneration', 'CU': 'Custom',
                'AS': 'Association', 'DS': 'Dissociation', 'BD': 'Binding',
            }
            cycle_type = full_type.split()[0] if full_type else "Custom"
            # Check if it's an abbreviation
            for abbr, full_name in type_map.items():
                if abbr in raw_type:
                    cycle_type = full_name
                    break
            # Also check tooltip for full name
            for full_name in type_map.values():
                if full_name.lower() in full_type.lower():
                    cycle_type = full_name
                    break

            # Parse duration from time column (format: 'Xm @ Ys')
            duration_minutes = 1.0  # default
            if time_item and time_item.text().strip():
                import re
                time_text = time_item.text().strip()
                min_match = re.search(r'(\d+\.?\d*)\s*m', time_text)
                if min_match:
                    duration_minutes = float(min_match.group(1))

            # Parse concentration
            conc_value = None
            conc_units = "nM"
            if conc_item and conc_item.text().strip():
                import re
                conc_text = conc_item.text().strip()
                numbers = re.findall(r'(\d+\.?\d*)', conc_text)
                if numbers:
                    conc_value = float(numbers[0])
                if 'ug/mL' in conc_text or 'µg/mL' in conc_text:
                    conc_units = "ug/mL"

            cycle_dict = {
                "type": cycle_type,
                "length_minutes": duration_minutes,
                "note": cycle_details.get('note', ''),
                "pumps": {},
                "contact_times": {},
            }

            # Add concentration if present
            if conc_value is not None:
                cycle_dict["concentration_value"] = conc_value
                cycle_dict["concentration_units"] = conc_units

            # Add flags if present
            flags_display = cycle_details.get('flags', '')
            if flags_display:
                cycle_dict["flags"] = flags_display

            cycle_dicts.append(cycle_dict)

        if not cycle_dicts:
            QMessageBox.information(
                self.main_window,
                "No Cycles",
                "No visible cycles to save. Load or record data first."
            )
            return

        # Prompt for method name
        method_name, ok = QInputDialog.getText(
            self.main_window,
            "Save Cycles as Method",
            f"Method name ({len(cycle_dicts)} cycles):",
            text="My Method"
        )

        if not ok or not method_name.strip():
            return

        # Get user profile
        try:
            if self.user_manager:
                username = self.user_manager.get_current_user() or "Default"
            else:
                # Fallback
                from affilabs.services.user_profile_manager import UserProfileManager
                user_mgr = UserProfileManager()
                username = user_mgr.get_current_user() or "Default"
        except Exception:
            username = "Default"

        # Default save directory
        default_dir = Path.home() / "Documents" / "Affilabs Methods" / username
        default_dir.mkdir(parents=True, exist_ok=True)

        # Sanitize filename
        safe_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in method_name.strip())
        default_path = str(default_dir / f"{safe_name}.json")

        file_path, _ = QFileDialog.getSaveFileName(
            self.main_window,
            "Save Method File",
            default_path,
            "JSON Files (*.json);;All Files (*.*)"
        )

        if not file_path:
            return

        try:
            method_data = {
                "version": "1.0",
                "name": method_name.strip(),
                "description": f"Created from Edit tab cycle table ({len(cycle_dicts)} cycles)",
                "author": username,
                "created": datetime.now().isoformat(),
                "source_experiment": "",
                "cycles": cycle_dicts,
                "cycle_count": len(cycle_dicts),
            }

            # Add experiment source metadata if available
            if (hasattr(self.main_window, 'app') and
                hasattr(self.main_window.app, 'current_experiment_folder') and
                self.main_window.app.current_experiment_folder):
                method_data["source_experiment"] = str(
                    self.main_window.app.current_experiment_folder.name
                )

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(method_data, f, indent=2, ensure_ascii=False)

            logger.info(f"✅ Saved {len(cycle_dicts)} cycles as method: {file_path}")

            QMessageBox.information(
                self.main_window,
                "Method Saved",
                f"Saved {len(cycle_dicts)} cycles as method:\n{file_path}\n\n"
                f"You can load this method in the Method Builder sidebar."
            )

        except Exception as e:
            logger.error(f"Failed to save method: {e}")
            QMessageBox.critical(
                self.main_window,
                "Save Failed",
                f"Failed to save method file:\n{str(e)}"
            )

    def _copy_table_to_clipboard(self):
        """Copy cycle table data to clipboard as tab-separated text."""
        from PySide6.QtWidgets import QMessageBox

        lines = []

        # Header row
        headers = []
        for col in range(self.cycle_data_table.columnCount()):
            if self.cycle_data_table.isColumnHidden(col):
                continue
            header_item = self.cycle_data_table.horizontalHeaderItem(col)
            headers.append(header_item.text().replace('\n', ' ') if header_item else f"Col{col}")
        lines.append('\t'.join(headers))

        # Data rows (selected rows if any, else all visible)
        selected_rows = set()
        for idx in self.cycle_data_table.selectionModel().selectedRows():
            selected_rows.add(idx.row())

        copied_count = 0
        for row in range(self.cycle_data_table.rowCount()):
            if self.cycle_data_table.isRowHidden(row):
                continue
            # If rows are selected, only copy those
            if selected_rows and row not in selected_rows:
                continue

            row_data = []
            for col in range(self.cycle_data_table.columnCount()):
                if self.cycle_data_table.isColumnHidden(col):
                    continue
                item = self.cycle_data_table.item(row, col)
                row_data.append(item.text() if item else "")
            lines.append('\t'.join(row_data))
            copied_count += 1

        if copied_count == 0:
            QMessageBox.information(
                self.main_window,
                "Nothing to Copy",
                "No visible data to copy."
            )
            return

        text = '\n'.join(lines)
        clipboard = QApplication.clipboard()
        clipboard.setText(text)

        logger.info(f"📋 Copied {copied_count} cycles to clipboard")

        # Brief feedback via tooltip on the export sidebar
        if hasattr(self.main_window, 'sidebar') and hasattr(self.main_window.sidebar, 'intel_message_label'):
            self.main_window.sidebar.intel_message_label.setText(
                f"📋 Copied {copied_count} cycles to clipboard"
            )
        else:
            # Show a brief status on the button itself
            QMessageBox.information(
                self.main_window,
                "Copied",
                f"Copied {copied_count} cycle{'s' if copied_count != 1 else ''} to clipboard.\n"
                "Paste into Excel, Google Sheets, or any spreadsheet."
            )

    def _export_for_external_software(self):
        """Export data formatted for external analysis software (GraphPad Prism, Origin, etc.)."""
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from datetime import datetime
        import csv

        # Collect visible rows with ΔSPR data
        rows = []
        for row in range(self.cycle_data_table.rowCount()):
            if self.cycle_data_table.isRowHidden(row):
                continue

            type_item = self.cycle_data_table.item(row, 1)
            conc_item = self.cycle_data_table.item(row, 3)
            dspr_item = self.cycle_data_table.item(row, 4)

            cycle_type = type_item.toolTip() if type_item and type_item.toolTip() else (type_item.text() if type_item else "")

            # Parse concentration
            conc_val = ""
            if conc_item and conc_item.text().strip():
                import re
                numbers = re.findall(r'(\d+\.?\d*)', conc_item.text())
                if numbers:
                    conc_val = numbers[0]

            # Parse ΔSPR per channel (format: 'A:val B:val C:val D:val')
            dspr_a = dspr_b = dspr_c = dspr_d = ""
            if dspr_item and dspr_item.text().strip():
                import re
                dspr_text = dspr_item.text()
                for ch_match in re.finditer(r'([ABCD]):([+-]?\d+\.?\d*)', dspr_text):
                    ch, val = ch_match.group(1), ch_match.group(2)
                    if ch == 'A': dspr_a = val
                    elif ch == 'B': dspr_b = val
                    elif ch == 'C': dspr_c = val
                    elif ch == 'D': dspr_d = val

            rows.append({
                "type": cycle_type,
                "concentration": conc_val,
                "dspr_a": dspr_a,
                "dspr_b": dspr_b,
                "dspr_c": dspr_c,
                "dspr_d": dspr_d,
            })

        if not rows:
            QMessageBox.information(
                self.main_window,
                "No Data",
                "No visible cycle data to export."
            )
            return

        # File dialog with user-specific default folder
        default_name = f"SPR_external_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        default_dir = self._get_user_export_dir()
        file_path, _ = QFileDialog.getSaveFileName(
            self.main_window,
            "Export for External Software",
            str(default_dir / default_name),
            "CSV Files (*.csv);;All Files (*.*)"
        )

        if not file_path:
            return

        try:
            # Write in column-oriented format suitable for Prism/Origin
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)

                # Header
                writer.writerow([
                    "Cycle Type", "Concentration",
                    "ΔSPR Ch A (RU)", "ΔSPR Ch B (RU)", "ΔSPR Ch C (RU)", "ΔSPR Ch D (RU)"
                ])

                for row in rows:
                    writer.writerow([
                        row["type"], row["concentration"],
                        row["dspr_a"], row["dspr_b"], row["dspr_c"], row["dspr_d"]
                    ])

            logger.info(f"✅ Exported {len(rows)} rows for external software: {file_path}")

            QMessageBox.information(
                self.main_window,
                "Export Successful",
                f"Exported {len(rows)} cycles to:\n{file_path}\n\n"
                "Format: CSV with columns for Concentration, ΔSPR per channel.\n"
                "Compatible with GraphPad Prism, Origin, and Excel."
            )

        except Exception as e:
            logger.error(f"Failed to export for external software: {e}")
            QMessageBox.critical(
                self.main_window,
                "Export Failed",
                f"Failed to export:\n{str(e)}"
            )

    def _export_table_data(self):
        """Export the cycle data table (analysis results) to CSV or Excel file."""
        from PySide6.QtWidgets import QFileDialog
        import csv
        from datetime import datetime
        from affilabs.utils.time_utils import filename_timestamp

        # Ensure experiment folder exists
        exp_folder = self._ensure_experiment_folder()

        # Get default save location in Analysis subfolder
        if exp_folder:
            analysis_folder = self.main_window.app.experiment_folder_mgr.get_subfolder_path(
                exp_folder, "Analysis"
            )
            default_name = f"Analysis_{filename_timestamp()}.xlsx"
            default_path = str(analysis_folder / default_name)
        else:
            # Fallback if no experiment folder
            default_name = f"Analysis_{filename_timestamp()}.xlsx"
            default_path = default_name

        # Open file dialog
        file_filter = "Excel Files (*.xlsx);;CSV Files (*.csv);;All Files (*.*)"
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self.main_window,
            "Export Analysis",
            default_path,
            file_filter
        )

        if not file_path:
            return  # User cancelled

        try:
            # Collect visible rows only (respect filter).
            # Score column (TABLE_COL_SCORE) is always included even if hidden in the UI —
            # it is analysis data and belongs in every export.
            score_col = getattr(self, 'TABLE_COL_SCORE', None)
            rows_data = []
            header = []

            # Get column headers — include Score even when hidden
            for col in range(self.cycle_data_table.columnCount()):
                hidden = self.cycle_data_table.isColumnHidden(col)
                if hidden and col != score_col:
                    continue
                header_item = self.cycle_data_table.horizontalHeaderItem(col)
                header.append(header_item.text().replace('\n', ' ') if header_item else f"Column {col}")

            # Append Quality Note header after Score
            if score_col is not None:
                header.append("Quality Note")

            rows_data.append(header)

            # Get visible row data
            details_cache = getattr(self, '_cycle_details_data', {})
            for row in range(self.cycle_data_table.rowCount()):
                if self.cycle_data_table.isRowHidden(row):
                    continue  # Skip filtered out rows

                row_data = []
                for col in range(self.cycle_data_table.columnCount()):
                    hidden = self.cycle_data_table.isColumnHidden(col)
                    if hidden and col != score_col:
                        continue  # Skip hidden columns except Score

                    item = self.cycle_data_table.item(row, col)
                    cell_value = item.text() if item else ""
                    # Strip the dot prefix from score cells for clean numeric export
                    if col == score_col and cell_value.startswith("● "):
                        cell_value = cell_value[2:]
                    row_data.append(cell_value)

                # Append quality note
                if score_col is not None:
                    det = details_cache.get(row, {})
                    row_data.append(det.get('quality_note', ''))

                rows_data.append(row_data)

            # Write to file
            if file_path.endswith('.xlsx'):
                # Excel export (if pandas available)
                try:
                    import pandas as pd
                    df = pd.DataFrame(rows_data[1:], columns=rows_data[0])
                    df.to_excel(file_path, index=False, engine='openpyxl')
                    logger.info(f"✅ Exported {len(rows_data)-1} cycles to Excel: {file_path}")
                except ImportError:
                    logger.warning("pandas not available, falling back to CSV export")
                    file_path = file_path.replace('.xlsx', '.csv')
                    self._write_csv(file_path, rows_data)
            else:
                # CSV export
                self._write_csv(file_path, rows_data)

            # Register file in experiment metadata (if using experiment folder)
            if exp_folder and Path(file_path).is_relative_to(exp_folder):
                self.main_window.app.experiment_folder_mgr.register_file(
                    exp_folder,
                    Path(file_path),
                    "analysis",
                    f"Cycle analysis table with {len(rows_data)-1} cycles"
                )
                logger.debug(f"Registered analysis file in experiment metadata")

            # Show success message
            if hasattr(self.main_window, 'sidebar') and hasattr(self.main_window.sidebar, 'intel_message_label'):
                self.main_window.sidebar.intel_message_label.setText(
                    f"✅ Exported {len(rows_data)-1} cycles to {file_path.split('/')[-1]}"
                )
                self.main_window.sidebar.intel_message_label.setStyleSheet(
                    "QLabel { font-size: 12px; color: #34C759; background: transparent; font-weight: 600; }"
                )

        except Exception as e:
            logger.error(f"Failed to export table data: {e}")
            if hasattr(self.main_window, 'sidebar') and hasattr(self.main_window.sidebar, 'intel_message_label'):
                self.main_window.sidebar.intel_message_label.setText(f"❌ Export failed: {str(e)}")

    def _write_csv(self, file_path, rows_data):
        """Write data to CSV file."""
        import csv
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows(rows_data)
        logger.info(f"✅ Exported {len(rows_data)-1} cycles to CSV: {file_path}")

    def _export_tracedrawer(self):
        """Open TraceDrawer export dialog.

        Passes the Edits tab's loaded cycle data, raw time-series, and
        alignment settings directly — no Excel loading needed.
        """
        from affilabs.dialogs.tracedrawer_export_dialog import TraceDrawerExportDialog

        # Collect cycles data from Edits tab
        cycles_data: list[dict] = []
        if hasattr(self.main_window, '_loaded_cycles_data') and self.main_window._loaded_cycles_data:
            cycles_data = list(self.main_window._loaded_cycles_data)

        if not cycles_data:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self.main_window,
                "No Cycle Data",
                "No cycles loaded in the Edits tab.\n"
                "Load an experiment first, then open TraceDrawer export.",
            )
            return

        # Collect raw data rows
        raw_data_rows: list[dict] = []
        try:
            raw_data_rows = self.main_window.app.recording_mgr.data_collector.raw_data_rows
        except AttributeError:
            pass

        if not raw_data_rows:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self.main_window,
                "No Raw Data",
                "No raw time-series data available.\n"
                "Record or load data before exporting.",
            )
            return

        # Collect alignment settings
        alignment: dict[int, dict] = {}
        if hasattr(self.main_window, '_cycle_alignment') and self.main_window._cycle_alignment:
            alignment = dict(self.main_window._cycle_alignment)

        dlg = TraceDrawerExportDialog(
            parent=self.main_window,
            cycles_data=cycles_data,
            raw_data_rows=raw_data_rows,
            alignment=alignment,
        )
        dlg.exec()
