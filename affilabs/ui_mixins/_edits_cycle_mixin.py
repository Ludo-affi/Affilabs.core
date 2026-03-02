"""EditsCycleMixin — Edits tab cycle, segment, Excel, reference, and demo data operations.

Extracted from affilabs/affilabs_core_ui.py (MainWindowPrototype).

Methods included (21 total):
    Edits delegators:
        _update_edits_selection_view      — delegates selection view update to EditsTab
        _toggle_edits_channel             — delegates channel toggle to EditsTab
        _export_edits_selection            — delegates selection export to EditsTab

    Excel / data loading:
        _load_data_from_excel             — opens file dialog, calls _load_data_from_excel_internal
        _load_data_from_excel_internal    — parses Excel sheets (Raw Data, Channel Data, Cycles, Metadata)
        _populate_edits_timeline_from_loaded_data — populates timeline graph from raw data rows

    Edits graph interaction:
        _on_edits_graph_clicked           — handles click on edits graph (flag add via FlagManager)
        _add_edits_flag                   — adds a flag to the edits graph (delegator)

    Cycle selection / alignment:
        _on_cycle_selected_in_table       — main cycle selection handler (402 lines, multi-select, RU conversion)
        _on_cycle_channel_changed         — handles channel selector change for a cycle row
        _on_cycle_shift_changed           — handles time shift change for a cycle row
        _update_channel_source_combos     — populates channel source dropdowns from selected cycles

    Segment management:
        _create_segment_from_selection    — creates EditableSegment from selected cycles
        _refresh_segment_list             — refreshes segment list dropdown
        _delete_selected_segment          — deletes currently selected segment
        _export_segment_to_tracedrawer    — exports segment to TraceDrawer CSV
        _export_segment_to_json           — exports segment to JSON
        _export_selected_segment_csv      — exports selected segment to CSV (convenience wrapper)
        _export_selected_segment_json     — exports selected segment to JSON (convenience wrapper)

    Reference traces:
        _clear_reference_graphs           — clears all 3 reference graphs
        _load_cycle_to_reference          — loads a cycle to a specific reference graph slot

    Utility:
        _find_nearest_index               — finds index of nearest time value in a list

    Demo data:
        _load_demo_data                   — loads synthetic SPR kinetics data for screenshots
"""

from __future__ import annotations

import logging

from PySide6.QtWidgets import QMenu, QMessageBox

logger = logging.getLogger(__name__)


class EditsCycleMixin:
    """Mixin providing cycle selection, segment, Excel, reference, and demo-data methods for MainWindowPrototype."""

    # ------------------------------------------------------------------
    # Edits delegators (L2452-L2465)
    # ------------------------------------------------------------------

    def _update_edits_selection_view(self):
        """Update edits selection view (delegates to EditsTab)."""
        if hasattr(self, 'edits_tab'):
            self.edits_tab._update_selection_view()

    def _toggle_edits_channel(self, ch_idx, visible):
        """Toggle edits channel visibility (delegates to EditsTab)."""
        if hasattr(self, 'edits_tab'):
            self.edits_tab._toggle_channel(ch_idx, visible)

    def _export_edits_selection(self):
        """Export edits selection (delegates to EditsTab)."""
        if hasattr(self, 'edits_tab'):
            self.edits_tab._export_selection()

    # ------------------------------------------------------------------
    # Excel / data loading (L2467-L2755)
    # ------------------------------------------------------------------

    def _load_data_from_excel(self):
        """Load previous acquisition data from Excel file for editing."""
        from PySide6.QtWidgets import QFileDialog

        # Open file dialog
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Excel File",
            "",
            "Excel Files (*.xlsx);All Files (*)"
        )

        if not file_path:
            return

        # Call internal load function
        self._load_data_from_excel_internal(file_path)

    def _load_data_from_excel_internal(self, file_path: str):
        """Internal function to load Excel data (used by both dialog and direct calls)."""
        from PySide6.QtWidgets import QMessageBox
        import pandas as pd

        try:
            logger.info(f"Loading Excel file: {file_path}")
            # Track source file so exports can pass-through the original XY data unchanged
            self._edits_source_file = file_path
            # Read all sheets
            excel_data = pd.read_excel(file_path, sheet_name=None, engine='openpyxl')

            # Load metadata from Metadata sheet
            loaded_metadata = {}
            if 'Metadata' in excel_data:
                df_meta = excel_data['Metadata']
                if 'key' in df_meta.columns and 'value' in df_meta.columns:
                    for _, row in df_meta.iterrows():
                        if pd.notna(row['key']) and pd.notna(row['value']):
                            loaded_metadata[str(row['key'])] = str(row['value'])
                    logger.info(f"✓ Loaded {len(loaded_metadata)} metadata items from Metadata sheet")
                else:
                    logger.warning(f"Metadata sheet missing 'key' or 'value' column. Found: {list(df_meta.columns)}")

            # Store loaded metadata for Edits tab
            self._loaded_metadata = loaded_metadata

            # Load raw data - try multiple formats in order of preference
            raw_data_rows = []

            # FORMAT 0: "Per-Channel Format" sheet — full experiment, RU values, preferred
            # Columns: Time_A, SPR_A, Time_B, SPR_B, Time_C, SPR_C, Time_D, SPR_D
            if 'Per-Channel Format' in excel_data:
                df_pc = excel_data['Per-Channel Format']
                logger.info(f"Loading from 'Per-Channel Format' sheet (full experiment, RU)")
                for ch in ['A', 'B', 'C', 'D']:
                    time_col = f'Time_{ch}'
                    spr_col = f'SPR_{ch}'
                    if time_col in df_pc.columns and spr_col in df_pc.columns:
                        for _, row in df_pc.iterrows():
                            if pd.notna(row[time_col]) and pd.notna(row[spr_col]):
                                raw_data_rows.append({
                                    'time': float(row[time_col]),
                                    'channel': ch.lower(),
                                    'value': float(row[spr_col]),  # already RU
                                    '_is_ru': True,
                                })
                logger.info(f"✓ Loaded {len(raw_data_rows)} data points from 'Per-Channel Format' sheet")

            # FORMAT 1: "Raw Data" sheet (current export format - simplest)
            elif 'Raw Data' in excel_data:
                df_raw = excel_data['Raw Data']
                logger.info(f"Loading from 'Raw Data' sheet with columns: {list(df_raw.columns)}")

                for idx, row in df_raw.iterrows():
                    if 'time' in row and 'channel' in row and 'value' in row:
                        raw_data_rows.append({
                            'time': float(row['time']),
                            'channel': str(row['channel']).lower(),
                            'value': float(row['value'])
                        })
                logger.info(f"✓ Loaded {len(raw_data_rows)} data points from 'Raw Data' sheet")

            # FORMAT 2: "Channel Data" sheet (current export format - side-by-side columns)
            elif 'Channel Data' in excel_data:
                df_channel = excel_data['Channel Data']
                logger.info(f"Loading from 'Channel Data' sheet with columns: {list(df_channel.columns)}")

                # Parse columns like "Time A (s)", "Channel A (nm)", "Time B (s)", "Channel B (nm)", etc.
                for ch in ['A', 'B', 'C', 'D']:
                    time_col = f"Time {ch} (s)"
                    value_col = f"Channel {ch} (nm)"

                    if time_col in df_channel.columns and value_col in df_channel.columns:
                        for idx, row in df_channel.iterrows():
                            if pd.notna(row[time_col]) and pd.notna(row[value_col]):
                                raw_data_rows.append({
                                    'time': float(row[time_col]),
                                    'channel': ch.lower(),
                                    'value': float(row[value_col])
                                })
                logger.info(f"✓ Loaded {len(raw_data_rows)} data points from 'Channel Data' sheet")

            # FORMAT 3: Old format - separate "Channel_A", "Channel_B" sheets (legacy)
            else:
                for sheet_name in ['Channel_A', 'Channel_B', 'Channel_C', 'Channel_D']:
                    if sheet_name in excel_data:
                        df = excel_data[sheet_name]
                        channel = sheet_name.split('_')[1].lower()  # 'a', 'b', 'c', or 'd'

                        # Convert DataFrame rows to raw data format
                        for idx, row in df.iterrows():
                            if 'Elapsed Time (s)' in row and 'Wavelength (nm)' in row:
                                raw_data_rows.append({
                                    'time': row['Elapsed Time (s)'],
                                    'channel': channel,
                                    'value': row['Wavelength (nm)']
                                })
                logger.info(f"✓ Loaded {len(raw_data_rows)} data points from legacy Channel_X sheets")

            # Load cycles table and parse time ranges
            cycles_data = []
            # Accept 'Cycles' or fallback to highest 'Cycles_vN' (version
            # manager may have rotated the canonical sheet on an earlier save).
            _cycles_sheet_name: str | None = None
            if 'Cycles' in excel_data:
                _cycles_sheet_name = 'Cycles'
            else:
                _vn = sorted(
                    [s for s in excel_data if s.startswith('Cycles_v')],
                    key=lambda s: int(s.rsplit('_v', 1)[-1]) if s.rsplit('_v', 1)[-1].isdigit() else 0,
                )
                if _vn:
                    _cycles_sheet_name = _vn[-1]  # highest version
                    logger.info(f"'Cycles' sheet not found — falling back to '{_cycles_sheet_name}'")
            if _cycles_sheet_name is not None:
                df_cycles = excel_data[_cycles_sheet_name]
                logger.info(f"Cycles sheet columns: {list(df_cycles.columns)}")

                # Check for duplicates and deduplicate if needed
                if 'cycle_id' in df_cycles.columns:
                    original_count = len(df_cycles)
                    df_cycles = df_cycles.drop_duplicates(subset=['cycle_id'], keep='first')
                    if len(df_cycles) < original_count:
                        logger.warning(f"Removed {original_count - len(df_cycles)} duplicate cycle rows based on cycle_id")
                elif 'cycle_num' in df_cycles.columns:
                    original_count = len(df_cycles)
                    df_cycles = df_cycles.drop_duplicates(subset=['cycle_num'], keep='first')
                    if len(df_cycles) < original_count:
                        logger.warning(f"Removed {original_count - len(df_cycles)} duplicate cycle rows based on cycle_num")

                for idx, row in df_cycles.iterrows():
                    # Debug: log first row to see what we're getting
                    if idx == 0:
                        logger.info(f"First cycle row data: {dict(row)}")

                    # Start with ALL Excel columns to preserve cycle_id, delta_spr, etc.
                    cycle_dict = {}
                    for col in df_cycles.columns:
                        val = row[col]
                        if pd.notna(val):
                            cycle_dict[col] = val

                    # Parse time range from ACh1 or start_time_sensorgram/end_time_sensorgram
                    if 'start_time_sensorgram' in df_cycles.columns and pd.notna(row['start_time_sensorgram']):
                        # Real software export format
                        start_time = float(row['start_time_sensorgram'])
                        end_time_raw = row.get('end_time_sensorgram', None)
                        end_time = float(end_time_raw) if pd.notna(end_time_raw) else start_time + 300
                    elif 'ACh1' in df_cycles.columns:
                        # Custom format with time range
                        time_range = str(row.get('ACh1', '0-0'))
                        if '-' in time_range:
                            start_str, end_str = time_range.split('-')
                            start_time = float(start_str)
                            end_time = float(end_str)
                        else:
                            start_time = 0.0
                            end_time = 0.0
                    else:
                        start_time = 0.0
                        end_time = 300.0

                    duration_min = (end_time - start_time) / 60.0

                    # Get type (handle both 'type' and 'Type')
                    cycle_type = row.get('type') if 'type' in df_cycles.columns else row.get('Type', 'Unknown')

                    # Get concentration (handle multiple formats)
                    if 'concentration_value' in df_cycles.columns:
                        concentration = row.get('concentration_value')
                    elif 'Conc.' in df_cycles.columns:
                        concentration = row.get('Conc.')
                    elif 'name' in df_cycles.columns:
                        concentration = row.get('name')
                    else:
                        concentration = ''

                    if pd.notna(concentration):
                        concentration = str(concentration)
                    else:
                        concentration = ''

                    # Get notes
                    notes = row.get('note') if 'note' in df_cycles.columns else row.get('Notes', '')

                    # Override with properly parsed values (preserving all other Excel columns)
                    cycle_dict.update({
                        'type': str(cycle_type) if pd.notna(cycle_type) else 'Unknown',
                        'duration_minutes': duration_min,
                        'start_time_sensorgram': start_time,
                        'end_time_sensorgram': end_time,
                        'concentration_value': concentration,
                        'note': str(notes) if pd.notna(notes) else '',
                        'channel': str(row.get('Channel', 'All')),
                        'shift': 0.0,
                    })

                    # Parse delta_spr_by_channel from string representation if present
                    dspr = cycle_dict.get('delta_spr_by_channel')
                    if isinstance(dspr, str):
                        import ast
                        try:
                            cycle_dict['delta_spr_by_channel'] = ast.literal_eval(dspr)
                        except Exception:
                            cycle_dict['delta_spr_by_channel'] = {}

                    # Parse concentrations dict from string representation if present
                    concs = cycle_dict.get('concentrations')
                    if isinstance(concs, str):
                        import ast
                        try:
                            cycle_dict['concentrations'] = ast.literal_eval(concs)
                        except Exception:
                            cycle_dict['concentrations'] = {}

                    # Parse flags from string list representation if present
                    flags_val = cycle_dict.get('flags', '')
                    if isinstance(flags_val, str) and flags_val.startswith('['):
                        import ast
                        try:
                            cycle_dict['flags'] = ast.literal_eval(flags_val)
                        except Exception:
                            cycle_dict['flags'] = flags_val
                    elif not flags_val or (isinstance(flags_val, float) and pd.isna(flags_val)):
                        cycle_dict['flags'] = ''

                    # Parse flag_data from string list representation if present
                    flag_data_val = cycle_dict.get('flag_data', [])
                    if isinstance(flag_data_val, str) and flag_data_val.startswith('['):
                        import ast
                        try:
                            cycle_dict['flag_data'] = ast.literal_eval(flag_data_val)
                        except Exception:
                            cycle_dict['flag_data'] = []
                    elif isinstance(flag_data_val, float) and pd.isna(flag_data_val):
                        cycle_dict['flag_data'] = []

                    cycles_data.append(cycle_dict)

                    # Debug log for first cycle
                    if idx == 0:
                        logger.info(f"First cycle parsed: type={cycle_type}, start={start_time}, end={end_time}, conc={concentration}")

            # Store loaded data in recording manager
            if hasattr(self.app, 'recording_mgr') and self.app.recording_mgr:
                # Clear existing data
                self.app.recording_mgr.data_collector.clear_all()

                # Populate with loaded data
                self.app.recording_mgr.data_collector.raw_data_rows = raw_data_rows
                self.app.recording_mgr.data_collector.cycles = cycles_data

                # Restore loaded metadata
                if loaded_metadata:
                    self.app.recording_mgr.data_collector.metadata = loaded_metadata
                    logger.info(f"Restored {len(loaded_metadata)} metadata items to data collector")

                logger.info(f"Loaded {len(raw_data_rows)} raw data points and {len(cycles_data)} cycles")
                logger.info(f"Data collector now has {len(self.app.recording_mgr.data_collector.raw_data_rows)} raw data rows")
            else:
                logger.warning("Recording manager not available - storing data in main window only")

            # Store cycles data for selection handling
            self._loaded_cycles_data = cycles_data

            # Update the edits tab with loaded cycles
            if hasattr(self, 'edits_tab'):
                # Pass loaded metadata to edits tab
                self.edits_tab._loaded_metadata = loaded_metadata
                self.edits_tab._populate_cycles_table(cycles_data)

                # Set timeline cursors to show all data (if they exist)
                if raw_data_rows and hasattr(self.edits_tab, 'edits_timeline_cursors'):
                    left_cursor = self.edits_tab.edits_timeline_cursors.get('left')
                    right_cursor = self.edits_tab.edits_timeline_cursors.get('right')
                    if left_cursor is not None and right_cursor is not None:
                        min_time = min(row['time'] for row in raw_data_rows)
                        max_time = max(row['time'] for row in raw_data_rows)
                        left_cursor.setValue(min_time)
                        right_cursor.setValue(max_time)

                # Update the selection view to show raw data
                if hasattr(self.edits_tab, '_update_selection_view'):
                    self.edits_tab._update_selection_view()

            # Sync ELN fields from Metadata sheet → ExperimentIndex so Notes tab
            # reflects whatever was saved (rating, tags, notes, kanban_status).
            # Non-critical: silently skip on any error.
            try:
                from pathlib import Path
                from affilabs.services.experiment_index import ExperimentIndex
                idx = ExperimentIndex()
                src_stem = Path(file_path).stem
                matched_id = None
                for entry in idx.all_entries():
                    ef = Path(entry.get("file", ""))
                    if ef.name == Path(file_path).name or ef.stem == src_stem:
                        matched_id = entry.get("id")
                        break
                if matched_id:
                    raw_rating = loaded_metadata.get("rating", "")
                    if raw_rating and raw_rating != "nan":
                        try:
                            idx.set_rating(matched_id, int(float(raw_rating)))
                        except (ValueError, TypeError):
                            pass
                    raw_tags = loaded_metadata.get("tags", "")
                    if raw_tags and raw_tags != "nan":
                        existing = idx.all_entries()
                        cur_tags = next((e.get("tags", []) for e in existing if e.get("id") == matched_id), [])
                        for t in [t.strip() for t in raw_tags.split(",") if t.strip()]:
                            if t not in cur_tags:
                                idx.add_tag(matched_id, t)
                    raw_notes = loaded_metadata.get("notes", "")
                    if raw_notes and raw_notes != "nan":
                        idx.update_notes(matched_id, raw_notes)
                    raw_status = loaded_metadata.get("kanban_status", "")
                    if raw_status in ("done", "to_repeat", "archived"):
                        idx.set_status(matched_id, raw_status)
                    logger.info(f"ELN fields synced from Metadata sheet → ExperimentIndex ({matched_id})")
            except Exception:
                pass

            # Enable Full Run button now that data is loaded
            try:
                edits_tab = getattr(self, 'edits_tab', None) or self
                btn = getattr(edits_tab, 'full_run_btn', None)
                if btn is not None:
                    btn.setEnabled(True)
            except Exception:
                pass

            if not getattr(self, '_suppress_load_dialog', False):
                QMessageBox.information(
                    self,
                    "Data Loaded",
                    f"Successfully loaded {len(cycles_data)} cycles from\n{file_path}"
                )

        except Exception as e:
            logger.error(f"Failed to load Excel file: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Load Error",
                f"Failed to load Excel file:\\n{str(e)}"
            )

    # ------------------------------------------------------------------
    # Edits timeline population (L6674-L6720)
    # ------------------------------------------------------------------

    def _populate_edits_timeline_from_loaded_data(self, raw_data: list):
        """Populate the timeline navigator graph with loaded raw data.

        Args:
            raw_data: List of raw data dictionaries with 'time', 'channel', 'value'
        """
        import numpy as np
        from affilabs.utils.logger import logger

        try:
            if not hasattr(self, 'edits_timeline_graph'):
                logger.warning("Timeline graph not found - cannot populate")
                return

            if not raw_data:
                logger.info("No raw data to display in timeline")
                return

            # Separate data by channel; track whether each channel's data is already RU.
            # _is_ru flag lives on the raw_data row dicts — checked BEFORE tuples are built.
            channel_data: dict[str, list[tuple]] = {'a': [], 'b': [], 'c': [], 'd': []}
            channel_is_ru: dict[str, bool] = {'a': False, 'b': False, 'c': False, 'd': False}

            for row in raw_data:
                channel = row.get('channel', '')
                time = row.get('time')
                value = row.get('value')

                if channel in channel_data and time is not None and value is not None:
                    channel_data[channel].append((time, value))
                    if row.get('_is_ru'):
                        channel_is_ru[channel] = True

            # Convert nm wavelength → ΔSPR (RU) per channel before plotting.
            # "Raw Data" sheet stores raw wavelength (nm); baseline = first valid point.
            WAVELENGTH_TO_RU = 355.0
            SPR_RANGE = (560.0, 720.0)

            # Plot each channel
            for ch_idx, ch in enumerate(['a', 'b', 'c', 'd']):
                if channel_data[ch]:
                    # Sort by time
                    channel_data[ch].sort(key=lambda x: x[0])
                    times = np.array([t for t, v in channel_data[ch]])
                    values = np.array([v for t, v in channel_data[ch]])

                    # Detect whether values need nm→RU conversion.
                    # Per-Channel Format sets channel_is_ru=True; Raw Data doesn't.
                    # Fallback heuristic: nm clusters around 560–720, RU around -500 to +5000.
                    already_ru = channel_is_ru[ch]
                    is_raw_nm = (not already_ru) and float(np.nanmedian(values)) > 400.0
                    if is_raw_nm:
                        # Find first valid baseline point in SPR range
                        baseline = None
                        for v in values:
                            if SPR_RANGE[0] <= v <= SPR_RANGE[1]:
                                baseline = float(v)
                                break
                        if baseline is None and len(values):
                            baseline = float(values[0])
                        baseline = baseline or 0.0
                        values = (values - baseline) * WAVELENGTH_TO_RU

                    # Plot on timeline graph
                    self.edits_timeline_curves[ch_idx].setData(times, values)
                    logger.debug(f"  Timeline: Plotted {len(times)} points for channel {ch}")
                else:
                    self.edits_timeline_curves[ch_idx].setData([], [])

            # Set cursor range to span the data
            if any(channel_data.values()):
                all_times = []
                for ch_data in channel_data.values():
                    all_times.extend([t for t, v in ch_data])

                if all_times:
                    min_time = min(all_times)
                    max_time = max(all_times)

                    # Set cursor positions to span data
                    self.edits_timeline_cursors['left'].setValue(min_time)
                    self.edits_timeline_cursors['right'].setValue(max_time)

                    # Trigger selection view update
                    self._update_edits_selection_view()

            logger.info(f"✓ Populated timeline graph with data from {len(raw_data)} rows")

        except Exception as e:
            logger.exception(f"Error populating timeline graph: {e}")

    # ------------------------------------------------------------------
    # Edits graph interaction (L6738-L6810)
    # ------------------------------------------------------------------

    def _on_edits_graph_clicked(self, event):
        """Handle mouse clicks on Edits graph for flag management.

        Delegates to FlagManager for unified flag handling.
        Left-click: Select/deselect flag
        Right-click: Show add-flag context menu
        """
        from PySide6.QtCore import Qt
        from affilabs.utils.logger import logger

        # Get click position in data coordinates
        view_box = self.edits_primary_graph.plotItem.vb
        mouse_point = view_box.mapSceneToView(event.scenePos())
        time_val = mouse_point.x()
        spr_val = mouse_point.y()

        # Get FlagManager reference
        flag_mgr = getattr(self.app, 'flag_mgr', None) if hasattr(self, 'app') else None
        if flag_mgr is None:
            logger.warning("FlagManager not available for edits flag handling")
            return

        # Handle left-click for flag selection (delegate to FlagManager)
        if event.button() == Qt.MouseButton.LeftButton:
            flag_mgr.try_select_edits_flag_near_click(time_val, spr_val)
            return

        # Handle right-click (context menu to add flag)
        if event.button() != Qt.MouseButton.RightButton:
            return

        # Check if we have cycle data loaded
        if not hasattr(self, '_loaded_cycles_data') or not self._loaded_cycles_data:
            logger.warning("No cycle data loaded - cannot add flags")
            return

        # Determine which channel to assign (use first visible channel or A)
        channel = 'A'

        # Show flag type menu — calls FlagManager.add_edits_flag()
        from PySide6.QtWidgets import QAction
        from PySide6.QtGui import QCursor

        menu = QMenu()

        injection_action = QAction("? Injection", menu)
        injection_action.triggered.connect(
            lambda: flag_mgr.add_edits_flag(channel, time_val, spr_val, "injection")
        )

        wash_action = QAction("🧪 Wash", menu)
        wash_action.triggered.connect(
            lambda: flag_mgr.add_edits_flag(channel, time_val, spr_val, "wash")
        )

        spike_action = QAction("? Spike", menu)
        spike_action.triggered.connect(
            lambda: flag_mgr.add_edits_flag(channel, time_val, spr_val, "spike")
        )

        menu.addAction(injection_action)
        menu.addAction(wash_action)
        menu.addAction(spike_action)

        menu.exec(QCursor.pos())

    def _add_edits_flag(self, channel: str, time_val: float, spr_val: float, flag_type: str):
        """Add a flag to the Edits graph — delegates to FlagManager."""
        flag_mgr = getattr(self.app, 'flag_mgr', None) if hasattr(self, 'app') else None
        if flag_mgr is not None:
            flag_mgr.add_edits_flag(channel, time_val, spr_val, flag_type)

    # ------------------------------------------------------------------
    # Cycle selection / alignment (L6811-L7309)
    # ------------------------------------------------------------------

    def _on_cycle_selected_in_table(self):
        """Handle cycle selection in table - load cycle data on graph.

        Supports multi-cycle selection for blending:
        - Single selection: Shows one cycle with baseline cursors
        - Multi-selection: Overlays all selected cycles
        - No selection: Clears the graph
        """
        from affilabs.utils.logger import logger

        try:
            # Get all selected rows
            selected_rows = sorted(set(item.row() for item in self.cycle_data_table.selectedItems()))

            if not selected_rows:
                # Clear graph when nothing is selected
                logger.info("[GRAPH] No cycles selected - clearing graph")
                for i in range(4):
                    self.edits_graph_curves[i].setData([], [])
                if hasattr(self, 'edits_graph_curve_labels'):
                    for lbl in self.edits_graph_curve_labels:
                        lbl.hide()
                # Hide time labels and legend when nothing selected
                if hasattr(self, 'edits_tab'):
                    for _lbl in ('alignment_start_time', 'alignment_end_time'):
                        w = getattr(self.edits_tab, _lbl, None)
                        if w:
                            w.setVisible(False)
                    leg = getattr(self.edits_tab, 'edits_spr_legend', None)
                    if leg:
                        leg.setVisible(False)
                return

            if len(selected_rows) == 1 and hasattr(self, 'edits_tab'):
                row_idx = selected_rows[0]

                # Update title with cycle number
                cycle_num = row_idx + 1  # 1-indexed for display
                self.edits_tab.alignment_title.setText(f"Cycle {cycle_num} Details & Editing")

                # Update graph context label with cycle type + concentration
                if hasattr(self.edits_tab, 'cycle_context_label') and row_idx < len(self._loaded_cycles_data):
                    _c = self._loaded_cycles_data[row_idx]
                    _type = _c.get('type', 'Cycle')
                    _conc = _c.get('concentration_value', '')
                    _conc_str = f" — {_conc}" if _conc and str(_conc).strip() not in ('', 'nan') else ''
                    self.edits_tab.cycle_context_label.setText(f"{_type} #{cycle_num}{_conc_str}")

                # Populate flags display
                if row_idx < len(self._loaded_cycles_data):
                    cycle = self._loaded_cycles_data[row_idx]
                    flags = cycle.get('flags', '')

                    if flags and flags.strip():
                        # Color code flags
                        flags_lower = flags.lower()
                        if any(word in flags_lower for word in ['error', 'fail', 'invalid', 'bad']):
                            flag_color = '#FF3B30'  # Red
                            flag_text = f"❌ {flags}"
                        elif any(word in flags_lower for word in ['warning', 'check', 'review']):
                            flag_color = '#FF9500'  # Orange
                            flag_text = f"⚠ {flags}"
                        else:
                            flag_color = '#007AFF'  # Blue
                            flag_text = f"🏷️ {flags}"

                        self.edits_tab.alignment_flags_display.setText(flag_text)
                        self.edits_tab.alignment_flags_display.setStyleSheet(f"""
                            font-size: 12px;
                            color: {flag_color};
                            font-weight: 600;
                        """)
                    else:
                        self.edits_tab.alignment_flags_display.setText("✓ None")
                        self.edits_tab.alignment_flags_display.setStyleSheet("""
                            font-size: 12px;
                            color: #34C759;
                            font-weight: 600;
                        """)

                # Populate alignment controls from stored data
                if not hasattr(self, '_cycle_alignment'):
                    self._cycle_alignment = {}
                alignment_data = self._cycle_alignment.get(row_idx, {'channel': 'All', 'shift': 0.0, 'ref': 'Global'})

                # Update channel combo
                self.edits_tab.alignment_channel_combo.blockSignals(True)
                self.edits_tab.alignment_channel_combo.setCurrentText(alignment_data['channel'])
                self.edits_tab.alignment_channel_combo.blockSignals(False)

                # Update reference combo
                if hasattr(self.edits_tab, 'alignment_ref_combo'):
                    ref_setting = alignment_data.get('ref', 'Global')
                    self.edits_tab.alignment_ref_combo.blockSignals(True)
                    self.edits_tab.alignment_ref_combo.setCurrentText(ref_setting)
                    self.edits_tab.alignment_ref_combo.blockSignals(False)

                # Update shift input and slider
                shift_value = alignment_data['shift']
                if hasattr(self.edits_tab, 'alignment_shift_input'):
                    self.edits_tab.alignment_shift_input.blockSignals(True)
                    self.edits_tab.alignment_shift_input.setText(f"{shift_value:.1f}")
                    self.edits_tab.alignment_shift_input.blockSignals(False)

                if hasattr(self.edits_tab, 'alignment_shift_slider'):
                    self.edits_tab.alignment_shift_slider.blockSignals(True)
                    slider_val = int(shift_value * 10)  # Convert to 0.1s increments
                    self.edits_tab.alignment_shift_slider.setValue(slider_val)
                    self.edits_tab.alignment_shift_slider.blockSignals(False)

                # Populate cycle boundary info
                if row_idx < len(self._loaded_cycles_data):
                    cycle = self._loaded_cycles_data[row_idx]
                    start_time = cycle.get('start_time', cycle.get('start_time_sensorgram', 0))
                    end_time = cycle.get('end_time', cycle.get('end_time_sensorgram'))

                    # Handle None values
                    if start_time is None:
                        start_time = 0.0
                    if end_time is None:
                        # Default to start_time + 5 minutes
                        duration_str = cycle.get('Duration (min)', '')
                        try:
                            duration_min = float(duration_str) if duration_str else 5.0
                        except:
                            duration_min = 5.0
                        end_time = start_time + (duration_min * 60)

                    # Update time labels in graph header
                    if hasattr(self.edits_tab, 'alignment_start_time'):
                        self.edits_tab.alignment_start_time.setText(f"▶ {start_time:.0f} s")
                        self.edits_tab.alignment_start_time.setVisible(True)
                    if hasattr(self.edits_tab, 'alignment_end_time'):
                        self.edits_tab.alignment_end_time.setText(f"◼ {end_time:.0f} s")
                        self.edits_tab.alignment_end_time.setVisible(True)
                    if hasattr(self.edits_tab, 'cycle_start_spinbox'):
                        self.edits_tab.cycle_start_spinbox.blockSignals(True)
                        self.edits_tab.cycle_start_spinbox.setValue(float(start_time))
                        self.edits_tab.cycle_start_spinbox.blockSignals(False)
                    if hasattr(self.edits_tab, 'cycle_end_spinbox'):
                        self.edits_tab.cycle_end_spinbox.blockSignals(True)
                        self.edits_tab.cycle_end_spinbox.setValue(float(end_time))
                        self.edits_tab.cycle_end_spinbox.blockSignals(False)
            elif hasattr(self, 'edits_tab'):
                # Hide time labels for multi-selection
                for _lbl in ('alignment_start_time', 'alignment_end_time'):
                    w = getattr(self.edits_tab, _lbl, None)
                    if w:
                        w.setVisible(False)

            # Get cycle data
            if not hasattr(self, '_loaded_cycles_data') or not self._loaded_cycles_data:
                logger.warning("No loaded cycle data available")
                return

            # Update channel source combos with selected cycle numbers
            self._update_channel_source_combos(selected_rows)

            # Collect all data from selected cycles
            all_cycle_data = {
                'a': {'time': [], 'wavelength': []},
                'b': {'time': [], 'wavelength': []},
                'c': {'time': [], 'wavelength': []},
                'd': {'time': [], 'wavelength': []},
            }

            valid_cycles_loaded = 0

            # --- Resolve data source ONCE outside the loop ---
            # Primary: raw_data_rows (populated from Excel or when recording)
            # Fallback: buffer_mgr.timeline_data (always populated during live acquisition)
            raw_data = None
            if hasattr(self.app, 'recording_mgr') and self.app.recording_mgr is not None:
                raw_data = self.app.recording_mgr.data_collector.raw_data_rows or None

            use_live_buffer = (
                not raw_data
                and hasattr(self.app, 'buffer_mgr')
                and self.app.buffer_mgr is not None
            )

            if not raw_data and not use_live_buffer:
                logger.warning("No data source available (no recording_mgr or buffer_mgr)")
                QMessageBox.warning(
                    self,
                    "No Data",
                    "No raw data available.\n\n"
                    "Start an acquisition or load an Excel file first."
                )
                return

            import math
            import numpy as np
            _CHANNEL_MAP = {'A': 'a', 'B': 'b', 'C': 'c', 'D': 'd', 'All': None}

            for row in selected_rows:
                if row >= len(self._loaded_cycles_data):
                    continue

                cycle = self._loaded_cycles_data[row]

                # Get time range for this cycle - try multiple field name variations
                # Use explicit None checks (not `or`) so start_time=0 is valid
                def _first_not_none(*keys):
                    for k in keys:
                        v = cycle.get(k)
                        if v is not None:
                            return v
                    return None

                start_time = _first_not_none(
                    'start_time_sensorgram', 'sensorgram_time',
                    'start_time', 'time', 'elapsed_time', 'elapsed',
                )
                end_time = _first_not_none('end_time_sensorgram', 'end_time')

                # Handle NaN values from pandas (convert to None)
                try:
                    if start_time is not None and isinstance(start_time, float) and math.isnan(start_time):
                        start_time = None
                    if end_time is not None and isinstance(end_time, float) and math.isnan(end_time):
                        end_time = None
                except (TypeError, ValueError):
                    pass

                if start_time is None:
                    logger.warning(f"Cycle {row} has no start time - available fields: {list(cycle.keys())}")
                    continue

                # If no end time, use start time + duration
                if end_time is None:
                    duration_min = cycle.get('duration_minutes', cycle.get('length_minutes', 5))
                    if duration_min is not None:
                        end_time = start_time + (duration_min * 60)
                    else:
                        end_time = start_time + 300  # 5 minutes default

                logger.info(f"[GRAPH] Loading cycle {row}: {start_time:.1f}s - {end_time:.1f}s")

                # Get alignment settings for this cycle
                cycle_channel = 'All'
                cycle_shift = 0.0
                if hasattr(self, '_cycle_alignment') and row in self._cycle_alignment:
                    cycle_channel = self._cycle_alignment[row]['channel']
                    cycle_shift = self._cycle_alignment[row]['shift']

                target_channel = _CHANNEL_MAP.get(cycle_channel)
                points_found = 0

                if use_live_buffer:
                    # --- Path B: Live buffer (numpy arrays, efficient slicing) ---
                    # Buffer stores RAW_ELAPSED coords but cycle times from to_export_dict()
                    # are in RECORDING coords.  Convert back to RAW for searchsorted.
                    _clock = getattr(self.app, 'clock', None)
                    if _clock is not None:
                        from affilabs.core.experiment_clock import TimeBase
                        _buf_start = _clock.convert(start_time, TimeBase.RECORDING, TimeBase.RAW_ELAPSED)
                        _buf_end = _clock.convert(end_time, TimeBase.RECORDING, TimeBase.RAW_ELAPSED)
                    else:
                        _buf_start, _buf_end = start_time, end_time
                    for ch in ['a', 'b', 'c', 'd']:
                        buf = self.app.buffer_mgr.timeline_data.get(ch)
                        if buf is None or len(buf.time) == 0:
                            continue
                        i_start = np.searchsorted(buf.time, _buf_start, side='left')
                        i_end = np.searchsorted(buf.time, _buf_end, side='right')
                        if i_start >= i_end:
                            continue
                        t_slice = buf.time[i_start:i_end]
                        w_slice = buf.wavelength[i_start:i_end]
                        if target_channel is None or ch == target_channel:
                            rel_times = (t_slice - _buf_start + cycle_shift).tolist()
                        else:
                            rel_times = (t_slice - _buf_start).tolist()
                        all_cycle_data[ch]['time'].extend(rel_times)
                        all_cycle_data[ch]['wavelength'].extend(w_slice.tolist())
                        points_found += len(t_slice)
                    logger.info(f"[GRAPH] Cycle {row}: {points_found} pts from live buffer")

                else:
                    # --- Path A: raw_data_rows (loaded Excel / recording) ---
                    for row_data in raw_data:
                        time_val = row_data.get('elapsed', row_data.get('time', 0))
                        if time_val > end_time:
                            break  # Data is time-ordered; past the window
                        if time_val < start_time:
                            continue
                        points_found += 1
                        if 'channel' in row_data and 'value' in row_data:
                            ch = row_data.get('channel')
                            value = row_data.get('value')
                            if ch in ['a', 'b', 'c', 'd'] and value is not None:
                                if target_channel is None or ch == target_channel:
                                    relative_time = time_val - start_time + cycle_shift
                                else:
                                    relative_time = time_val - start_time
                                all_cycle_data[ch]['time'].append(relative_time)
                                all_cycle_data[ch]['wavelength'].append(value)
                        else:
                            for ch in ['a', 'b', 'c', 'd']:
                                wavelength = row_data.get(f'channel_{ch}', row_data.get(f'wavelength_{ch}'))
                                if wavelength is not None:
                                    if target_channel is None or ch == target_channel:
                                        relative_time = time_val - start_time + cycle_shift
                                    else:
                                        relative_time = time_val - start_time
                                    all_cycle_data[ch]['time'].append(relative_time)
                                    all_cycle_data[ch]['wavelength'].append(wavelength)
                    logger.info(f"[GRAPH] Cycle {row}: {points_found} pts from raw_data_rows")

                if points_found > 0:
                    valid_cycles_loaded += 1

            # Check if any valid cycles were loaded
            if valid_cycles_loaded == 0:
                logger.warning("No valid cycles could be loaded - all cycles missing start time")
                QMessageBox.warning(
                    self,
                    "No Valid Cycles",
                    "Selected cycles are missing start time information.\n\n"
                    "This usually means the data was not recorded properly."
                )
                return

            # Apply reference subtraction if configured
            ref_channel_idx = None
            if len(selected_rows) == 1 and hasattr(self.edits_tab, '_get_effective_ref_channel'):
                ref_channel_idx = self.edits_tab._get_effective_ref_channel(selected_rows[0])
                if ref_channel_idx is not None:
                    ref_channel_name = ['a', 'b', 'c', 'd'][ref_channel_idx]
                    ref_time = np.array(all_cycle_data[ref_channel_name]['time'])
                    ref_wavelength = np.array(all_cycle_data[ref_channel_name]['wavelength'])

                    if len(ref_time) > 0:
                        logger.info(f"[REF SUBTRACT] Using Ch {ref_channel_name.upper()} as reference ({len(ref_time)} points)")

                        # Sort reference data by time
                        ref_sort_idx = np.argsort(ref_time)
                        ref_time = ref_time[ref_sort_idx]
                        ref_wavelength = ref_wavelength[ref_sort_idx]

                        # Subtract reference from each channel (except the reference itself)
                        for ch in ['a', 'b', 'c', 'd']:
                            if ch == ref_channel_name:
                                continue  # Don't subtract reference from itself

                            ch_time = np.array(all_cycle_data[ch]['time'])
                            ch_wavelength = np.array(all_cycle_data[ch]['wavelength'])

                            if len(ch_time) > 0:
                                # Sort channel data by time
                                ch_sort_idx = np.argsort(ch_time)
                                ch_time_sorted = ch_time[ch_sort_idx]
                                ch_wavelength_sorted = ch_wavelength[ch_sort_idx]

                                # Interpolate reference to match channel time points
                                ref_interp = np.interp(ch_time_sorted, ref_time, ref_wavelength,
                                                      left=np.nan, right=np.nan)

                                # Subtract reference (only where we have valid interpolation)
                                valid_mask = ~np.isnan(ref_interp)
                                ch_wavelength_subtracted = ch_wavelength_sorted.copy()
                                ch_wavelength_subtracted[valid_mask] -= ref_interp[valid_mask]

                                # CRITICAL: keep only the subtracted points.
                                # Points outside the reference time range keep their raw
                                # absolute wavelength (~620 nm). Mixing raw and
                                # differential values in the same array causes the
                                # baseline correction to produce ±200,000 RU spikes.
                                all_cycle_data[ch]['time'] = ch_time_sorted[valid_mask].tolist()
                                all_cycle_data[ch]['wavelength'] = ch_wavelength_subtracted[valid_mask].tolist()

                                logger.info(f"[REF SUBTRACT] Ch {ch.upper()}: subtracted {valid_mask.sum()}/{len(ch_time)} points")
                    else:
                        logger.warning(f"[REF SUBTRACT] Reference channel {ref_channel_name.upper()} has no data")

            # Plot the collected data on the graph
            # Conversion factor: 1 nm wavelength shift = 355 RU
            WAVELENGTH_TO_RU = 355.0

            for i, ch in enumerate(['a', 'b', 'c', 'd']):
                time_data = np.array(all_cycle_data[ch]['time'])
                wavelength_data = np.array(all_cycle_data[ch]['wavelength'])

                if len(time_data) > 0:
                    # Sort by time (important for proper line plotting!)
                    sort_indices = np.argsort(time_data)
                    time_data = time_data[sort_indices]
                    wavelength_data = wavelength_data[sort_indices]

                    # Apply baseline correction (subtract first point) and convert to RU
                    baseline = wavelength_data[0]
                    delta_wavelength = wavelength_data - baseline
                    spr_data = delta_wavelength * WAVELENGTH_TO_RU

                    # Apply smoothing if slider is set
                    smooth_slider = getattr(self, 'edits_smooth_slider', None)
                    smooth_win = smooth_slider.value() if smooth_slider else 0
                    if smooth_win > 1 and len(spr_data) > smooth_win:
                        from scipy.ndimage import uniform_filter1d
                        spr_data = uniform_filter1d(spr_data, size=smooth_win, mode='nearest')

                    self.edits_graph_curves[i].setData(time_data, spr_data)
                    # Update channel label to right edge of curve
                    if hasattr(self, 'edits_graph_curve_labels') and i < len(self.edits_graph_curve_labels):
                        lbl = self.edits_graph_curve_labels[i]
                        lbl.setPos(time_data[-1], spr_data[-1])
                        lbl.show()
                    logger.info(f"[GRAPH] Ch {ch.upper()}: {len(time_data)} pts, time {time_data.min():.1f}-{time_data.max():.1f}s, baseline={baseline:.3f}nm, RU range {spr_data.min():.1f} to {spr_data.max():.1f}")
                else:
                    # Clear curve if no data
                    self.edits_graph_curves[i].setData([], [])
                    if hasattr(self, 'edits_graph_curve_labels') and i < len(self.edits_graph_curve_labels):
                        self.edits_graph_curve_labels[i].hide()
                    logger.info(f"[GRAPH] No data for channel {ch.upper()}")

            # Auto-scale the graph to show all data
            self.edits_primary_graph.autoRange()
            # Update Y-axis label to show RU
            self.edits_primary_graph.setLabel('left', 'Response (RU)')
            logger.info("[GRAPH] Auto-scaled graph to fit data")

            # Show floating legend as soon as a cycle is on the graph
            if hasattr(self, 'edits_tab'):
                _leg = getattr(self.edits_tab, 'edits_spr_legend', None)
                if _leg is not None and not _leg.isVisible():
                    _leg.setVisible(True)
                    self.edits_tab._position_edits_legend()

            # Style curves — mirror live Active Cycle graph exactly:
            # • reference channel: dashed, semi-transparent purple (153,102,255,150)
            # • other channels: palette colour + active line style
            import pyqtgraph as pg
            from PySide6.QtCore import Qt as _Qt
            from affilabs.settings import settings as _settings
            _ch_keys = ['a', 'b', 'c', 'd']
            _pen_style = _Qt.PenStyle(_settings.ACTIVE_LINE_STYLE)

            def _ch_color(i):
                raw = _settings.ACTIVE_GRAPH_COLORS.get(_ch_keys[i], "#1D1D1F")
                if isinstance(raw, str) and raw.startswith('#'):
                    raw = raw.lstrip('#')
                    return tuple(int(raw[j:j+2], 16) for j in (0, 2, 4))
                return raw  # already (r,g,b)

            for i in range(4):
                if ref_channel_idx is not None and i == ref_channel_idx:
                    self.edits_graph_curves[i].setPen(
                        pg.mkPen(color=(153, 102, 255, 150), width=2,
                                 style=_Qt.PenStyle.DashLine)
                    )
                else:
                    self.edits_graph_curves[i].setPen(
                        pg.mkPen(color=_ch_color(i), width=2, style=_pen_style)
                    )

            logger.info(f"✓ Loaded {valid_cycles_loaded} cycle(s) to edits graph")

            # Handle baseline cursors (only for single selection)
            if len(selected_rows) == 1:
                row = selected_rows[0]
                cycle = self._loaded_cycles_data[row]
                start_time = cycle.get('start_time_sensorgram', cycle.get('sensorgram_time'))
                end_time = cycle.get('end_time_sensorgram')

                # Skip cursor creation if no valid start time
                if start_time is None:
                    logger.warning(f"Cycle {row} has no start time - skipping cursor creation")
                else:
                    if end_time is None:
                        duration_min = cycle.get('duration_minutes', cycle.get('length_minutes', 5))
                        if duration_min is not None:
                            end_time = start_time + (duration_min * 60)
                        else:
                            end_time = start_time + 300  # 5 minutes default

            # Update barchart with new cycle data
            if hasattr(self, 'edits_tab'):
                self.edits_tab._update_delta_spr_barchart()

        except Exception as e:
            logger.exception(f"Error loading cycle data to edits graph: {e}")

    def _on_cycle_channel_changed(self, channel_text):
        """Handle channel selector change for a cycle row.

        Args:
            channel_text: Selected channel ("All", "A", "B", "C", or "D")
        """
        from affilabs.utils.logger import logger

        try:
            # Get the cycle index from the sender widget
            sender = self.sender()
            if not sender:
                return

            cycle_idx = sender.property('cycle_index')
            if cycle_idx is None:
                return

            # Update alignment settings
            if not hasattr(self, '_cycle_alignment'):
                self._cycle_alignment = {}

            if cycle_idx not in self._cycle_alignment:
                self._cycle_alignment[cycle_idx] = {'channel': 'All', 'shift': 0.0}

            self._cycle_alignment[cycle_idx]['channel'] = channel_text
            logger.info(f"[ALIGNMENT] Cycle {cycle_idx} channel set to: {channel_text}")

            # Refresh the graph if this cycle is selected
            self._on_cycle_selected_in_table()

        except Exception as e:
            logger.exception(f"Error handling cycle channel change: {e}")

    def _on_cycle_shift_changed(self, shift_value):
        """Handle time shift change for a cycle row.

        Args:
            shift_value: Time shift in seconds
        """
        from affilabs.utils.logger import logger

        try:
            # Get the cycle index from the sender widget
            sender = self.sender()
            if not sender:
                return

            cycle_idx = sender.property('cycle_index')
            if cycle_idx is None:
                return

            # Update alignment settings
            if not hasattr(self, '_cycle_alignment'):
                self._cycle_alignment = {}

            if cycle_idx not in self._cycle_alignment:
                self._cycle_alignment[cycle_idx] = {'channel': 'All', 'shift': 0.0}

            self._cycle_alignment[cycle_idx]['shift'] = shift_value
            logger.info(f"[ALIGNMENT] Cycle {cycle_idx} shift set to: {shift_value:.2f}s")

            # Refresh the graph if this cycle is selected
            self._on_cycle_selected_in_table()

        except Exception as e:
            logger.exception(f"Error handling cycle shift change: {e}")

    def _update_channel_source_combos(self, selected_rows: list):
        """Update channel source dropdown options based on selected cycles.

        Args:
            selected_rows: List of selected table row indices
        """
        from affilabs.utils.logger import logger

        try:
            if not hasattr(self, 'channel_source_combos'):
                return

            # Clear and repopulate all channel combos
            for ch_idx in range(4):
                combo = self.channel_source_combos[ch_idx]
                combo.clear()
                combo.addItem("Auto")  # Default option

                # Add each selected cycle as an option
                for row in selected_rows:
                    if row < len(self._loaded_cycles_data):
                        cycle = self._loaded_cycles_data[row]
                        cycle_type = cycle.get('type', 'Unknown')
                        combo.addItem(f"Cycle {row + 1} ({cycle_type})", row)

            logger.debug(f"Updated channel source combos with {len(selected_rows)} cycles")

        except Exception as e:
            logger.exception(f"Error updating channel source combos: {e}")

    # ------------------------------------------------------------------
    # Segment management (L7311-L7790)
    # ------------------------------------------------------------------

    def _create_segment_from_selection(self):
        """Create an EditableSegment from currently selected cycles.

        Uses channel source combos to determine which cycle contributes to each channel.
        """
        from PySide6.QtWidgets import QMessageBox, QInputDialog
        from affilabs.utils.logger import logger

        try:
            # Get selected cycles
            selected_rows = sorted(set(item.row() for item in self.cycle_data_table.selectedItems()))

            if not selected_rows:
                QMessageBox.warning(
                    self,
                    "No Selection",
                    "Please select one or more cycles to create a segment."
                )
                return

            if not hasattr(self, '_loaded_cycles_data') or not self._loaded_cycles_data:
                QMessageBox.warning(
                    self,
                    "No Data",
                    "No cycle data loaded."
                )
                return

            # Get cycle data (keep as dictionaries)
            source_cycles = []
            for row in selected_rows:
                if row < len(self._loaded_cycles_data):
                    cycle_dict = self._loaded_cycles_data[row]
                    source_cycles.append(cycle_dict)

            if not source_cycles:
                QMessageBox.warning(
                    self,
                    "Invalid Selection",
                    "Selected cycles could not be loaded."
                )
                return

            # Get channel sources from combos
            channel_sources = {}
            for ch_idx in range(4):
                combo = self.channel_source_combos[ch_idx]
                selected_index = combo.currentIndex()

                if selected_index == 0:  # "Auto"
                    # Use first selected cycle for this channel
                    channel_sources[ch_idx] = selected_rows[0]
                else:
                    # Use the cycle selected in combo
                    cycle_row = combo.currentData()
                    if cycle_row is not None:
                        channel_sources[ch_idx] = cycle_row
                    else:
                        channel_sources[ch_idx] = selected_rows[0]

            # Ask user for segment name
            segment_name, ok = QInputDialog.getText(
                self,
                "Create Segment",
                "Enter segment name:",
                text=f"Segment_{len(source_cycles)}_cycles"
            )

            if not ok or not segment_name:
                return

            # Create segment using SegmentManager
            if not hasattr(self.app, 'segment_mgr'):
                QMessageBox.warning(
                    self,
                    "Not Ready",
                    "Segment manager not initialized."
                )
                return

            # Determine time range (union of all selected cycles)
            min_start = min(c.get('start_time_sensorgram', c.get('sensorgram_time', 0)) for c in source_cycles)
            max_end = max(c.get('end_time_sensorgram', min_start + 300) for c in source_cycles)
            time_range = (min_start, max_end)

            # Create segment
            segment = self.app.segment_mgr.create_segment(
                name=segment_name,
                source_cycles=source_cycles,
                time_range=time_range,
                channel_sources=channel_sources
            )

            # Refresh segment list
            self._refresh_segment_list()

            QMessageBox.information(
                self,
                "Segment Created",
                f"Created segment '{segment_name}' from {len(source_cycles)} cycle(s).\n\n"
                f"Time range: {min_start:.1f}s - {max_end:.1f}s"
            )

            logger.info(f"✓ Created segment '{segment_name}' from {len(source_cycles)} cycles")

        except Exception as e:
            logger.exception(f"Error creating segment: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to create segment: {str(e)}"
            )

    def _refresh_segment_list(self):
        """Refresh the segment list dropdown with current segments."""
        from affilabs.utils.logger import logger

        try:
            if not hasattr(self, 'segment_list_combo'):
                return

            if not hasattr(self.app, 'segment_mgr'):
                return

            # Clear current list
            self.segment_list_combo.clear()

            # Get all segments
            segments = self.app.segment_mgr.list_segments()

            if segments:
                for segment_name in segments:
                    self.segment_list_combo.addItem(segment_name)
            else:
                self.segment_list_combo.addItem("(no segments yet)")

            logger.debug(f"Refreshed segment list: {len(segments)} segments")

        except Exception as e:
            logger.exception(f"Error refreshing segment list: {e}")

    def _delete_selected_segment(self):
        """Delete currently selected segment."""
        from affilabs.utils.logger import logger

        try:
            if not hasattr(self, 'segment_list_combo'):
                return

            segment_name = self.segment_list_combo.currentText()

            if segment_name == "(no segments yet)" or not segment_name:
                QMessageBox.warning(
                    self,
                    "No Selection",
                    "Please select a segment to delete."
                )
                return

            # Confirm deletion
            reply = QMessageBox.question(
                self,
                "Confirm Delete",
                f"Are you sure you want to delete segment '{segment_name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

            # Delete segment
            if hasattr(self.app, 'segment_mgr'):
                self.app.segment_mgr.delete_segment(segment_name)

                # Update segment list
                self._refresh_segment_list()

                QMessageBox.information(
                    self,
                    "Segment Deleted",
                    f"Deleted segment '{segment_name}'."
                )

                logger.info(f"✓ Deleted segment '{segment_name}'")

        except Exception as e:
            logger.exception(f"Error deleting segment: {e}")
            QMessageBox.critical(
                self,
                "Delete Error",
                f"Failed to delete segment: {str(e)}"
            )

    def _export_segment_to_tracedrawer(self, segment_name: str):
        """Export a segment to TraceDrawer CSV format.

        Args:
            segment_name: Name of segment to export
        """
        from PySide6.QtWidgets import QFileDialog
        from affilabs.utils.logger import logger

        try:
            if not hasattr(self.app, 'segment_mgr'):
                QMessageBox.warning(
                    self,
                    "Not Ready",
                    "Segment manager not initialized."
                )
                return

            # Get segment
            segment = self.app.segment_mgr.get_segment(segment_name)
            if segment is None:
                QMessageBox.warning(
                    self,
                    "Not Found",
                    f"Segment '{segment_name}' not found."
                )
                return

            # Ask for save location
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export to TraceDrawer CSV",
                f"{segment_name}.csv",
                "CSV Files (*.csv)"
            )

            if not file_path:
                return

            # Export using segment's method
            segment.export_to_tracedrawer_csv(file_path)

            QMessageBox.information(
                self,
                "Export Complete",
                f"Exported segment '{segment_name}' to:\n{file_path}"
            )

            logger.info(f"✓ Exported segment '{segment_name}' to TraceDrawer CSV")

        except Exception as e:
            logger.exception(f"Error exporting segment: {e}")
            QMessageBox.critical(
                self,
                "Export Error",
                f"Failed to export segment: {str(e)}"
            )

    def _export_segment_to_json(self, segment_name: str):
        """Export a segment to JSON format for re-import.

        Args:
            segment_name: Name of segment to export
        """
        from PySide6.QtWidgets import QFileDialog
        from affilabs.utils.logger import logger

        try:
            if not hasattr(self.app, 'segment_mgr'):
                QMessageBox.warning(
                    self,
                    "Not Ready",
                    "Segment manager not initialized."
                )
                return

            # Ask for save location
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Segment to JSON",
                f"{segment_name}.json",
                "JSON Files (*.json)"
            )

            if not file_path:
                return

            # Export using manager's method
            self.app.segment_mgr.export_segment(segment_name, file_path)

            QMessageBox.information(
                self,
                "Export Complete",
                f"Exported segment '{segment_name}' to:\n{file_path}"
            )

            logger.info(f"✓ Exported segment '{segment_name}' to JSON")

        except Exception as e:
            logger.exception(f"Error exporting segment to JSON: {e}")
            QMessageBox.critical(
                self,
                "Export Error",
                f"Failed to export segment: {str(e)}"
            )

    def _export_selected_segment_csv(self):
        """Export currently selected segment to TraceDrawer CSV format."""
        from affilabs.utils.logger import logger

        try:
            if not hasattr(self, 'segment_list_combo'):
                return

            segment_name = self.segment_list_combo.currentText()

            if segment_name == "(no segments yet)" or not segment_name:
                QMessageBox.warning(
                    self,
                    "No Selection",
                    "Please select a segment to export."
                )
                return

            self._export_segment_to_tracedrawer(segment_name)

        except Exception as e:
            logger.exception(f"Error exporting selected segment to CSV: {e}")

    def _export_selected_segment_json(self):
        """Export currently selected segment to JSON format."""
        from affilabs.utils.logger import logger

        try:
            if not hasattr(self, 'segment_list_combo'):
                return

            segment_name = self.segment_list_combo.currentText()

            if segment_name == "(no segments yet)" or not segment_name:
                QMessageBox.warning(
                    self,
                    "No Selection",
                    "Please select a segment to export."
                )
                return

            self._export_segment_to_json(segment_name)

        except Exception as e:
            logger.exception(f"Error exporting selected segment to JSON: {e}")

    # ------------------------------------------------------------------
    # Reference traces (L7424-L7555)
    # ------------------------------------------------------------------

    def _clear_reference_graphs(self):
        """Clear all reference graphs."""
        from affilabs.utils.logger import logger

        try:
            if not hasattr(self, 'edits_reference_curves'):
                return

            for i in range(3):
                # Clear all curves
                for curve in self.edits_reference_curves[i]:
                    curve.setData([], [])

                # Reset label
                self.edits_reference_labels[i].setText("Drag cycle here")
                self.edits_reference_labels[i].setStyleSheet(
                    "QLabel {"
                    "  font-size: 12px;"
                    "  color: {Colors.SECONDARY_TEXT};"
                    "  background: {Colors.TRANSPARENT};"
                    "  font-family: {Fonts.SYSTEM};"
                    "}",
                )

                # Reset stored data
                self.edits_reference_cycle_data[i] = None

            logger.info("✓ Cleared all reference graphs")

        except Exception as e:
            logger.exception(f"Error clearing reference graphs: {e}")

    def _load_cycle_to_reference(self, cycle_row: int, ref_index: int):
        """Load a cycle to a specific reference graph.

        Args:
            cycle_row: Row index of cycle in table
            ref_index: Index of reference graph (0-2)
        """
        from affilabs.utils.logger import logger

        try:
            if not hasattr(self, '_loaded_cycles_data') or not self._loaded_cycles_data:
                logger.warning("No loaded cycle data available")
                return

            if cycle_row >= len(self._loaded_cycles_data):
                return

            if ref_index < 0 or ref_index >= 3:
                logger.warning(f"Invalid reference index: {ref_index}")
                return

            cycle = self._loaded_cycles_data[cycle_row]

            # Get time range for this cycle
            start_time = cycle.get('start_time_sensorgram', cycle.get('sensorgram_time'))
            end_time = cycle.get('end_time_sensorgram')

            if start_time is None:
                logger.warning(f"Cycle {cycle_row} has no start time - cannot load to reference")
                QMessageBox.warning(
                    self,
                    "Invalid Cycle",
                    f"Cycle {cycle_row + 1} is missing start time information and cannot be displayed."
                )
                return

            # If no end time, use start time + duration
            if end_time is None:
                duration_min = cycle.get('duration_minutes', cycle.get('length_minutes', 5))
                if duration_min is not None:
                    end_time = start_time + (duration_min * 60)
                else:
                    end_time = start_time + 300  # 5 minutes default

            # Load raw data from loaded Excel
            if not hasattr(self, '_loaded_raw_data') or not self._loaded_raw_data:
                logger.warning("No loaded data available")
                return

            # Get raw data (list of dicts with 'time', 'channel', 'value')
            raw_data = self._loaded_raw_data

            # Filter data for this cycle's time range
            cycle_data = {
                'a': {'time': [], 'wavelength': []},
                'b': {'time': [], 'wavelength': []},
                'c': {'time': [], 'wavelength': []},
                'd': {'time': [], 'wavelength': []},
            }

            for row_data in raw_data:
                time = row_data.get('time', 0)
                if start_time <= time <= end_time:
                    ch = row_data.get('channel', '')
                    if ch in ['a', 'b', 'c', 'd']:
                        value = row_data.get('value')
                        if value is not None:
                            cycle_data[ch]['time'].append(time)
                            cycle_data[ch]['wavelength'].append(value)

            # Update reference graph
            for ch_idx, ch in enumerate(['a', 'b', 'c', 'd']):
                if cycle_data[ch]['time']:
                    self.edits_reference_curves[ref_index][ch_idx].setData(
                        cycle_data[ch]['time'],
                        cycle_data[ch]['wavelength']
                    )
                else:
                    self.edits_reference_curves[ref_index][ch_idx].setData([], [])

            # Update label
            cycle_type = cycle.get('type', 'Unknown')
            self.edits_reference_labels[ref_index].setText(f"{cycle_type} {cycle_row + 1}")
            self.edits_reference_labels[ref_index].setStyleSheet(
                "QLabel {"
                "  font-size: 12px;"
                "  color: {Colors.PRIMARY_TEXT};"
                "  font-weight: 600;"
                "  background: {Colors.TRANSPARENT};"
                "  font-family: {Fonts.SYSTEM};"
                "}",
            )

            # Store cycle data
            self.edits_reference_cycle_data[ref_index] = cycle_row

            logger.info(f"✓ Loaded {cycle_type} cycle {cycle_row + 1} to reference {ref_index + 1}")

        except Exception as e:
            logger.exception(f"Error loading cycle to reference: {e}")

    # ------------------------------------------------------------------
    # Utility (L7792-L7812)
    # ------------------------------------------------------------------

    def _find_nearest_index(self, time_list: list, target_time: float) -> int | None:
        """Find index of time value nearest to target time.

        Args:
            time_list: List of time values
            target_time: Target time to find

        Returns:
            Index of nearest time value, or None if list is empty
        """
        if not time_list:
            return None

        min_diff = float('inf')
        nearest_idx = 0

        for idx, time_val in enumerate(time_list):
            diff = abs(time_val - target_time)
            if diff < min_diff:
                min_diff = diff
                nearest_idx = idx

        return nearest_idx

    # ------------------------------------------------------------------
    # Demo data (L7814-L7940)
    # ------------------------------------------------------------------

    def _load_demo_data(self):
        """Load demo SPR kinetics data for promotional screenshots.

        Keyboard shortcut: Ctrl+Shift+D
        Generates realistic binding curves with association/dissociation phases.
        """
        try:
            from affilabs.utils.demo_data_generator import generate_demo_cycle_data

            # Generate 3 cycles of demo data with increasing responses
            time_array, channel_data, cycle_boundaries = generate_demo_cycle_data(
                num_cycles=3,
                cycle_duration=600,
                sampling_rate=2.0,
                responses=[20, 40, 65],  # Progressive concentration series
                seed=42,
            )

            # Check if app instance is available (it should be set by main_simplified)
            if not hasattr(self, "app") or self.app is None:
                print("⚠️  Demo data: No app instance available")
                print(
                    "   Demo data can only be loaded when running through main_simplified.py",
                )
                from PySide6.QtWidgets import QMessageBox

                QMessageBox.warning(
                    self,
                    "Demo Data Unavailable",
                    "Demo data can only be loaded when the application is fully initialized.\n\n"
                    "Please ensure you're running through main_simplified.py",
                )
                return

            # Access the data manager through the app instance
            data_mgr = self.app.data_mgr

            # Load demo data into buffers using the proper buffer update mechanism
            # The data manager will handle converting to the right format
            for i, time_point in enumerate(time_array):
                # Update time buffer
                if i == 0:
                    # Initialize
                    data_mgr.time_buffer = []
                    data_mgr.wavelength_buffer_a = []
                    data_mgr.wavelength_buffer_b = []
                    data_mgr.wavelength_buffer_c = []
                    data_mgr.wavelength_buffer_d = []

                data_mgr.time_buffer.append(time_point)
                data_mgr.wavelength_buffer_a.append(channel_data["a"][i])
                data_mgr.wavelength_buffer_b.append(channel_data["b"][i])
                data_mgr.wavelength_buffer_c.append(channel_data["c"][i])
                data_mgr.wavelength_buffer_d.append(channel_data["d"][i])

            # Now update the timeline data in buffer manager
            import numpy as np

            for ch in ["a", "b", "c", "d"]:
                if hasattr(self.app, "buffer_mgr") and hasattr(
                    self.app.buffer_mgr,
                    "timeline_data",
                ):
                    self.app.buffer_mgr.timeline_data[ch].time = np.array(time_array)
                    self.app.buffer_mgr.timeline_data[ch].wavelength = np.array(
                        channel_data[ch],
                    )

            # Trigger graph updates for both full timeline and cycle of interest
            # Update full timeline graph
            if hasattr(self, "full_timeline_graph"):
                for ch_idx, ch in enumerate(["a", "b", "c", "d"]):
                    if ch_idx < len(self.full_timeline_graph.curves):
                        curve = self.full_timeline_graph.curves[ch_idx]
                        curve.setData(time_array, channel_data[ch])

            # Update cycle of interest graph
            if hasattr(self.app, "_update_cycle_of_interest_graph"):
                self.app._update_cycle_of_interest_graph()

            print(
                f"✅ Demo data loaded: {len(time_array)} points, {len(cycle_boundaries)} cycles",
            )
            print("   Use this view for promotional screenshots")

            # Show confirmation message
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.information(
                self,
                "Demo Data Loaded",
                f"Loaded {len(cycle_boundaries)} cycles of demo SPR kinetics data.\n\n"
                "The sensorgram now shows realistic binding curves for promotional use.\n"
                f"Total duration: {time_array[-1]:.0f} seconds\n"
                f"Data points: {len(time_array)}\n\n"
                "Tip: Navigate to different views to capture various screenshots.",
            )

        except ImportError as e:
            print(f"❌ Error importing demo data generator: {e}")
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.critical(
                self,
                "Import Error",
                f"Could not import demo data generator:\n{e}",
            )
        except Exception as e:
            print(f"❌ Error loading demo data: {e}")
            import traceback

            try:
                print(traceback.format_exc())
            except:
                pass
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.critical(
                self,
                "Error Loading Demo Data",
                f"An error occurred while loading demo data:\n\n{e!s}\n\n"
                "Please check the console for details.",
            )
