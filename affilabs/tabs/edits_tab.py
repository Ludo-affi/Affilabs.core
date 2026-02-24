"""Edits Tab - Data review and cycle editing functionality.

Assembles the EditsTab class from mixin modules in the edits/ package.
This tab provides:
- Full timeline navigation with dual cursors
- Active selection view with baseline correction
- Cycle table for data management
- Export and segment creation tools
"""

import re

import pandas as pd
from PySide6.QtWidgets import QPushButton

from affilabs.utils.logger import logger
from affilabs.tabs.edits._data_mixin import DataMixin
from affilabs.tabs.edits._export_mixin import ExportMixin
from affilabs.tabs.edits._ui_builders import UIBuildersMixin
from affilabs.tabs.edits._alignment_mixin import AlignmentMixin
from affilabs.tabs.edits._table_mixin import TableMixin
from affilabs.tabs.edits._binding_plot_mixin import BindingPlotMixin


class EditsTab(DataMixin, ExportMixin, UIBuildersMixin, AlignmentMixin, TableMixin, BindingPlotMixin):
    """Handles the Edits tab UI and logic."""
    
    # Constants for consistent channel handling
    CHANNELS = ['A', 'B', 'C', 'D']
    CHANNELS_LOWER = ['a', 'b', 'c', 'd']
    
    # Table column indices for cycle data table
    TABLE_COL_EXPORT = 0
    TABLE_COL_TYPE = 1
    TABLE_COL_TIME = 2
    TABLE_COL_CONC = 3
    TABLE_COL_DELTA_SPR = 4

    def __init__(self, main_window):
        """Initialize Edits tab with reference to main window.

        Args:
            main_window: AffilabsMainWindow instance
        """
        self.main_window = main_window

        # Get shared user profile manager from main app
        self.user_manager = None
        if hasattr(main_window, 'app') and hasattr(main_window.app, 'user_profile_manager'):
            self.user_manager = main_window.app.user_profile_manager

        # Loaded metadata from Excel file (populated when loading file)
        self._loaded_metadata = {}
        self._loaded_file_path = None  # Path to the currently loaded Excel file (for saving)

        # Per-cycle editing state
        self._cycle_alignment = {}  # {row_idx: {'channel': str, 'shift': float}}

        # Binding plot fit result cache (populated by BindingPlotMixin._update_binding_plot)
        self._binding_fit_result = None

        # Rmax calculator state (§12 of EDITS_BINDING_PLOT_FRS)
        self._ligand_mw: float | None = None
        self._analyte_mw: float | None = None
        self._immob_delta_spr_ru: float | None = None

        # Flags system for marking/annotating graph points
        # NOTE: _edits_flags and _selected_flag_idx are now managed by FlagManager.
        # These properties delegate to FlagManager for backward compatibility.
        # Direct list is kept as fallback if FlagManager is not available.
        self._edits_flags_fallback = []
        self._selected_flag_idx = None

        # Delta SPR cursor locking state
        self._delta_spr_cursor_locked = False  # Whether cursors are locked to contact_time
        self._delta_spr_lock_distance = 0.0  # Locked distance between cursors (contact_time + 10%)
        self._suppressing_position_change = False  # Flag to prevent recursive cursor updates

        # UI elements (will be created in create_content)
        self.cycle_data_table = None
        self.edits_timeline_graph = None
        self.edits_primary_graph = None
        self.edits_timeline_curves = []
        self.edits_graph_curves = []
        self.edits_timeline_cursors = {'left': None, 'right': None}
        self.edits_cycle_markers = []
        self.edits_cycle_labels = []
        self.edits_smooth_slider = None
        self.edits_smooth_label = None
        self.delta_spr_lock_btn = None  # Lock/unlock button

    def _update_metadata_stats(self):
        """Update metadata statistics based on loaded metadata or current table data."""
        if not hasattr(self, 'meta_total_cycles'):
            return

        # Check if we have loaded metadata from Excel file
        loaded_metadata = getattr(self, '_loaded_metadata', {})

        # CYCLES COUNT: Always count from table (dynamic)
        total_visible = 0
        cycle_types = set()
        concentrations = []

        for row in range(self.cycle_data_table.rowCount()):
            if not self.cycle_data_table.isRowHidden(row):
                total_visible += 1

                # Get cycle type (col 1 — after Export checkbox)
                type_item = self.cycle_data_table.item(row, 1)
                if type_item:
                    tip = type_item.toolTip()  # Full type name e.g. 'Baseline 1'
                    if tip:
                        cycle_types.add(tip.split()[0])
                    else:
                        cycle_types.add(type_item.text())

                # Get concentration (col 3)
                conc_item = self.cycle_data_table.item(row, 3)
                if conc_item and conc_item.text().strip():
                    try:
                        # Try to extract number from text like "10 nM" or "[High] 10 nM"
                        conc_text = conc_item.text().strip()
                        # Extract numbers
                        numbers = re.findall(r'\d+\.?\d*', conc_text)
                        if numbers:
                            conc_val = float(numbers[0])
                            concentrations.append(conc_val)
                    except (ValueError, IndexError):
                        pass

        # Update cycle count
        self.meta_total_cycles.setText(f"{total_visible}")

        # Update cycle types
        if cycle_types:
            types_text = ", ".join(sorted(cycle_types))
            if len(types_text) > 30:
                types_text = types_text[:27] + "..."
            self.meta_cycle_types.setText(types_text)
        else:
            self.meta_cycle_types.setText("-")

        # Update concentration range
        if concentrations:
            min_conc = min(concentrations)
            max_conc = max(concentrations)
            self.meta_conc_range.setText(f"{min_conc:.2e} - {max_conc:.2e}")
        else:
            self.meta_conc_range.setText("-")

        # DATE: Prefer loaded metadata, fall back to recording_mgr or today
        from datetime import datetime
        date_str = None

        if loaded_metadata and 'recording_start' in loaded_metadata:
            date_str = loaded_metadata['recording_start']
            # If it's ISO format, convert to readable format
            if 'recording_start_iso' in loaded_metadata:
                try:
                    dt_obj = datetime.fromisoformat(loaded_metadata['recording_start_iso'])
                    date_str = dt_obj.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    pass  # Use the string as-is
        elif hasattr(self.main_window, 'app') and hasattr(self.main_window.app, 'recording_mgr'):
            rec = self.main_window.app.recording_mgr
            if hasattr(rec, 'recording_start_time') and rec.recording_start_time:
                date_str = rec.recording_start_time.strftime("%Y-%m-%d %H:%M")

        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")

        self.meta_date.setText(date_str)

        # METHOD: Prefer loaded metadata
        method_str = None

        if loaded_metadata and 'method_name' in loaded_metadata:
            method_str = loaded_metadata['method_name']
        elif loaded_metadata and 'Method' in loaded_metadata:
            method_str = loaded_metadata['Method']

        self.meta_method.setText(method_str if method_str else "-")

        # OPERATOR: Prefer loaded metadata, fall back to current user
        operator_str = None

        if loaded_metadata and 'operator' in loaded_metadata:
            operator_str = loaded_metadata['operator']
        elif loaded_metadata and 'User' in loaded_metadata:
            operator_str = loaded_metadata['User']
        else:
            try:
                if self.user_manager:
                    user = self.user_manager.get_current_user()
                else:
                    # Fallback
                    from affilabs.services.user_profile_manager import UserProfileManager
                    user_mgr = UserProfileManager()
                    user = user_mgr.get_current_user()
                operator_str = user if user else None
            except Exception:
                pass

        self.meta_operator.setText(operator_str if operator_str else "-")

        # DEVICE: Prefer loaded metadata, fall back to current device.
        # Mask supplier prefix "FLMT" → "AFFI" for customer-facing display.
        device_str = None

        if loaded_metadata and 'device_id' in loaded_metadata:
            device_str = loaded_metadata['device_id']
        elif hasattr(self.main_window, 'device_config') and self.main_window.device_config:
            dc = self.main_window.device_config
            device_id = getattr(dc, 'device_serial', '') or ''
            device_str = device_id if device_id else None

        if device_str:
            import re as _re
            device_str = _re.sub(r'(?i)^FLMT', 'AFFI', device_str)

        self.meta_device.setText(device_str if device_str else "-")

        # CALIBRATION: name of the startup calibration JSON used for this session.
        # Prefer explicit metadata key, then look at latest_calibration.json timestamp,
        # then fall back to calibration_service's last saved path.
        if not hasattr(self, 'meta_calibration'):
            return  # widget not yet built (guard during early init)

        cal_str = None
        if loaded_metadata and 'calibration_file' in loaded_metadata:
            cal_str = loaded_metadata['calibration_file']
        else:
            try:
                from pathlib import Path as _Path
                import json as _json
                _cal_dir = _Path("calibration_results")
                _latest = _cal_dir / "latest_calibration.json"
                if _latest.exists():
                    with open(_latest) as _f:
                        _meta = _json.load(_f).get("calibration_metadata", {})
                    _ts = _meta.get("timestamp", "")
                    if _ts:
                        # Convert ISO timestamp to filename: calibration_YYYYMMDD_HHMMSS.json
                        from datetime import datetime as _dt
                        _dt_obj = _dt.fromisoformat(_ts)
                        cal_str = f"calibration_{_dt_obj.strftime('%Y%m%d_%H%M%S')}.json"
            except Exception:
                pass

        self.meta_calibration.setText(cal_str if cal_str else "-")

        # TRANSMISSION BASELINE FILE: the Excel file from a baseline recording.
        # Prefer explicit metadata key, then try the current recording's output file.
        trans_str = None
        if loaded_metadata and 'transmission_file' in loaded_metadata:
            trans_str = loaded_metadata['transmission_file']
        elif loaded_metadata and 'baseline_file' in loaded_metadata:
            trans_str = loaded_metadata['baseline_file']
        else:
            try:
                from pathlib import Path as _Path2
                _rec = getattr(getattr(self.main_window, 'app', None), 'recording_mgr', None)
                if _rec and getattr(_rec, 'current_file', None):
                    trans_str = _Path2(_rec.current_file).name
            except Exception:
                pass

        self.meta_transmission_file.setText(trans_str if trans_str else "-")

        # RATING + TAGS: from ExperimentIndex, keyed by loaded file path
        if hasattr(self, 'meta_star_buttons'):
            entry = self._find_index_entry_for_file(getattr(self, '_loaded_file_path', None))
            rating = entry.get("rating", 0) if entry else 0
            self._set_star_display(rating)
            tags = entry.get("tags", []) if entry else []
            self._refresh_tags_display(tags)

    # ── ExperimentIndex integration ───────────────────────────────────────────

    def _find_index_entry_for_file(self, file_path) -> dict | None:
        """Return the ExperimentIndex entry whose 'file' field matches file_path, or None."""
        if not file_path:
            return None
        try:
            from pathlib import Path as _P
            from affilabs.services.experiment_index import ExperimentIndex
            idx = ExperimentIndex()
            abs_path = _P(file_path).resolve()
            base = (_P.home() / "Documents" / "Affilabs Data").resolve()
            # Build both relative and absolute forms for comparison
            try:
                rel = str(abs_path.relative_to(base))
            except ValueError:
                rel = None
            abs_str = str(abs_path)
            for entry in idx.all_entries():
                entry_file = entry.get("file", "")
                # Match against relative path first, then absolute
                if rel and (entry_file == rel or entry_file.replace("\\", "/") == rel.replace("\\", "/")):
                    return entry
                if entry_file == abs_str or _P(entry_file).resolve() == abs_path:
                    return entry
        except Exception:
            pass
        return None

    def _set_star_display(self, rating: int) -> None:
        """Update the 5 star buttons to reflect the given rating (0 = none filled)."""
        for i, btn in enumerate(self.meta_star_buttons, start=1):
            if i <= rating:
                btn.setStyleSheet(btn.styleSheet().replace("color: #D1D1D6", "color: #FF9500")
                                  if "color: #FF9500" not in btn.styleSheet() else btn.styleSheet())
                # Simpler: set inline color per button
                btn.setProperty("active", True)
            else:
                btn.setProperty("active", False)
            # Force repaint via individual style
            filled = i <= rating
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                    font-size: 16px;
                    color: {"#FF9500" if filled else "#D1D1D6"};
                    padding: 0px;
                }}
                QPushButton:hover {{ color: #FF9500; }}
            """)

    def _on_star_clicked(self, n: int) -> None:
        """Toggle or set star rating. Clicking the current rating clears it (sets to 0)."""
        entry = self._find_index_entry_for_file(getattr(self, '_loaded_file_path', None))
        if not entry:
            return
        try:
            from affilabs.services.experiment_index import ExperimentIndex
            idx = ExperimentIndex()
            current = entry.get("rating", 0)
            new_rating = 0 if current == n else n
            idx.set_rating(entry["id"], new_rating)
            self._set_star_display(new_rating)
        except Exception:
            pass

    def _refresh_tags_display(self, tags: list) -> None:
        """Rebuild the tag pills container to show current tags."""
        layout = self._meta_tags_pills_layout
        # Clear all existing pill widgets (keep the stretch at the end)
        while layout.count() > 1:
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        # Add a pill per tag
        for tag in tags:
            pill = QPushButton(f"{tag}  ✕")
            pill.setFixedHeight(20)
            pill.setStyleSheet(f"""
                QPushButton {{
                    background: #E3F0FF;
                    border: 1px solid #B0D0FF;
                    border-radius: 10px;
                    font-size: 10px;
                    color: #007AFF;
                    padding: 0px 8px;
                }}
                QPushButton:hover {{
                    background: #FFE5E5;
                    border-color: #FF3B30;
                    color: #FF3B30;
                }}
            """)
            _t = tag
            pill.clicked.connect(lambda checked, t=_t: self._on_tag_removed(t))
            layout.insertWidget(layout.count() - 1, pill)

    def _on_tag_added(self) -> None:
        """Read tag from input, write to index, refresh display."""
        tag = self.meta_tag_input.text().strip().lower()
        if not tag:
            return
        entry = self._find_index_entry_for_file(getattr(self, '_loaded_file_path', None))
        if not entry:
            return
        try:
            from affilabs.services.experiment_index import ExperimentIndex
            idx = ExperimentIndex()
            idx.add_tag(entry["id"], tag)
            # Re-read to get updated tags
            updated = self._find_index_entry_for_file(self._loaded_file_path)
            self._refresh_tags_display(updated.get("tags", []) if updated else [])
            self.meta_tag_input.clear()
        except Exception:
            pass

    def _on_tag_removed(self, tag: str) -> None:
        """Remove a tag from the index entry and refresh display."""
        entry = self._find_index_entry_for_file(getattr(self, '_loaded_file_path', None))
        if not entry:
            return
        try:
            from affilabs.services.experiment_index import ExperimentIndex
            idx = ExperimentIndex()
            idx.remove_tag(entry["id"], tag)
            updated = self._find_index_entry_for_file(self._loaded_file_path)
            self._refresh_tags_display(updated.get("tags", []) if updated else [])
        except Exception:
            pass

    def _update_selection_view(self):
        """Update active selection graph based on timeline cursor positions."""
        # Check for recording manager and raw data
        if not hasattr(self.main_window.app, 'recording_mgr') or not self.main_window.app.recording_mgr:
            return

        raw_data = self.main_window.app.recording_mgr.data_collector.raw_data_rows
        if not raw_data:
            return

        # Check if cursors exist
        if not self.edits_timeline_cursors.get('left') or not self.edits_timeline_cursors.get('right'):
            return

        # Get cursor positions
        left_pos = self.edits_timeline_cursors['left'].value()
        right_pos = self.edits_timeline_cursors['right'].value()

        if left_pos > right_pos:
            left_pos, right_pos = right_pos, left_pos

        # Filter and plot data
        smoothing = self.edits_smooth_slider.value() if self.edits_smooth_slider else 0

        for ch_idx, ch in enumerate(self.CHANNELS_LOWER):
            times = []
            wavelengths = []

            # Filter rows for this channel within time range
            for row in raw_data:
                # New simple format: {time, channel, value}
                row_channel = row.get('channel', '')
                if row_channel != ch:
                    continue  # Skip other channels

                time = row.get('time', 0)
                value = row.get('value')

                if left_pos <= time <= right_pos:
                    if pd.notna(time) and pd.notna(value):
                        times.append(time)
                        wavelengths.append(value)

            if times:
                import numpy as np
                times = np.array(times)
                wavelengths = np.array(wavelengths)
                sort_idx = np.argsort(times)
                times = times[sort_idx]
                wavelengths = wavelengths[sort_idx]

                # Baseline correction and convert to RU
                if len(wavelengths) > 0:
                    baseline = wavelengths[0]
                    rus = (wavelengths - baseline) * 355.0

                    # Apply smoothing if enabled
                    if smoothing > 0 and len(rus) > smoothing:
                        from scipy.ndimage import uniform_filter1d
                        rus = uniform_filter1d(rus, size=smoothing, mode='nearest')

                    # Normalize time to start at 0
                    times = times - times[0]

                    self.edits_graph_curves[ch_idx].setData(times, rus)
            else:
                self.edits_graph_curves[ch_idx].setData([], [])

        self.edits_primary_graph.autoRange()

        # Call main window's delta SPR update if it exists
        if hasattr(self.main_window, '_update_edits_delta_spr'):
            self.main_window._update_edits_delta_spr()

    def _get_raw_data_untouched(self) -> pd.DataFrame:
        """Get original XY data without any processing applied."""
        # Option 1: From "Send to Edits" - wide format DataFrame
        if hasattr(self.main_window, '_edits_raw_data') and self.main_window._edits_raw_data is not None:
            return self.main_window._edits_raw_data.copy()

        # Option 2: From loaded Excel file - preserve raw data sheet
        elif hasattr(self.main_window, '_loaded_raw_data_sheets'):
            if 'Raw_Data' in self.main_window._loaded_raw_data_sheets:
                return self.main_window._loaded_raw_data_sheets['Raw_Data'].copy()
            elif 'Channels XY' in self.main_window._loaded_raw_data_sheets:
                return self.main_window._loaded_raw_data_sheets['Channels XY'].copy()

        # Option 3: Construct from buffer_mgr (live data)
        elif hasattr(self.main_window, 'app') and hasattr(self.main_window.app, 'buffer_mgr'):
            return self._extract_raw_from_buffer()

        # Fallback: empty DataFrame
        logger.warning("No raw data source available for untouched export")
        return pd.DataFrame()

    def _extract_raw_from_buffer(self) -> pd.DataFrame:
        """Extract raw XY data from buffer manager in wide format."""
        try:
            buffer_mgr = self.main_window.app.buffer_mgr
            channels = self.CHANNELS

            raw_data = {}
            for ch in channels:
                if hasattr(buffer_mgr.cycle_data[ch], 'time') and hasattr(buffer_mgr.cycle_data[ch], 'wavelength'):
                    raw_data[f'Time_{ch}'] = buffer_mgr.cycle_data[ch].time
                    raw_data[f'SPR_{ch}'] = buffer_mgr.cycle_data[ch].wavelength

            return pd.DataFrame(raw_data) if raw_data else pd.DataFrame()

        except Exception as e:
            logger.error(f"Failed to extract raw data from buffer: {e}")
            return pd.DataFrame()

    def _get_processed_data_with_edits(self) -> pd.DataFrame:
        """Generate processed curves with current UI settings applied."""
        raw_df = self._get_raw_data_untouched()

        if raw_df.empty:
            return pd.DataFrame()

        processed_df = raw_df.copy()

        # Apply current smoothing if enabled
        if hasattr(self, 'edits_smooth_slider') and self.edits_smooth_slider.value() > 0:
            processed_df = self._apply_smoothing_to_dataframe(processed_df, level=self.edits_smooth_slider.value())

        # Apply baseline correction (uses first wavelength value as reference)
        processed_df = self._apply_baseline_correction_to_dataframe(processed_df)

        # Apply time shifts and channel alignments would go here if implemented
        # processed_df = self._apply_time_alignments(processed_df)
        # processed_df = self._apply_channel_alignments(processed_df)

        return processed_df

    def _apply_smoothing_to_dataframe(self, df: pd.DataFrame, level: int) -> pd.DataFrame:
        """Apply smoothing to SPR columns in DataFrame."""
        processed_df = df.copy()

        # Apply smoothing to SPR columns
        for col in df.columns:
            if col.startswith('SPR_'):
                if level > 0:
                    # Simple rolling mean smoothing
                    window_size = min(level + 1, len(df))
                    processed_df[col] = df[col].rolling(window=window_size, center=True).mean()
                    # Fill NaN values at edges (pandas 2.x+ compatible)
                    processed_df[col] = processed_df[col].bfill().ffill()

        return processed_df

    def _apply_baseline_correction_to_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply baseline correction to SPR columns."""
        processed_df = df.copy()

        # Apply baseline correction to SPR columns
        for col in df.columns:
            if col.startswith('SPR_') and not df[col].empty:
                # Use first value as baseline
                baseline = df[col].iloc[0] if len(df[col]) > 0 else 0
                processed_df[col] = df[col] - baseline

        return processed_df

    def _get_current_analysis_results(self) -> pd.DataFrame:
        """Capture current delta SPR measurements and cursor states."""
        results = []

        if not hasattr(self.main_window, '_loaded_cycles_data'):
            return pd.DataFrame()

        for row_idx, cycle in enumerate(self.main_window._loaded_cycles_data):
            # Current delta measurements (from _update_delta_spr_barchart)
            delta_data = {
                'Cycle_ID': cycle.get('cycle_id', f'Cycle_{row_idx+1}'),
                'Contact_Time': cycle.get('contact_time'),
                'Delta_SPR_A': getattr(self, 'current_delta_values', [None, None, None, None])[0],
                'Delta_SPR_B': getattr(self, 'current_delta_values', [None, None, None, None])[1],
                'Delta_SPR_C': getattr(self, 'current_delta_values', [None, None, None, None])[2],
                'Delta_SPR_D': getattr(self, 'current_delta_values', [None, None, None, None])[3],
                'Cursor_Start': getattr(self.delta_spr_start_cursor, 'value', lambda: None)() if hasattr(self, 'delta_spr_start_cursor') else None,
                'Cursor_Stop': getattr(self.delta_spr_stop_cursor, 'value', lambda: None)() if hasattr(self, 'delta_spr_stop_cursor') else None,
                'Locked_Distance': getattr(self, '_delta_spr_lock_distance', None) if getattr(self, '_delta_spr_cursor_locked', False) else None,
                'Lock_Active': getattr(self, '_delta_spr_cursor_locked', False)
            }
            results.append(delta_data)

        return pd.DataFrame(results)

    def _get_updated_flag_positions(self) -> pd.DataFrame:
        """Get updated flag marker positions with metadata."""
        flag_results = []

        if not hasattr(self.main_window, '_loaded_cycles_data'):
            return pd.DataFrame()

        for cycle in self.main_window._loaded_cycles_data:
            cycle_id = cycle.get('cycle_id', 'Unknown')
            flag_data = cycle.get('flag_data', [])

            for flag in flag_data:
                flag_entry = {
                    'Cycle_ID': cycle_id,
                    'Flag_Type': flag.get('type', 'unknown'),
                    'Channel': flag.get('channel', 'unknown'),
                    'Time_Position': flag.get('time', 0),
                    'SPR_Value': flag.get('spr', 0),
                    'Confidence': flag.get('confidence', 1.0),
                    'Is_Reference': flag.get('is_reference', False)
                }
                flag_results.append(flag_entry)

        return pd.DataFrame(flag_results)

    def _get_enriched_cycles_metadata(self) -> pd.DataFrame:
        """Get cycle data with processing settings documentation."""
        from datetime import datetime

        if not hasattr(self.main_window, '_loaded_cycles_data'):
            return pd.DataFrame()

        cycles = [cycle.copy() for cycle in self.main_window._loaded_cycles_data]

        # Add processing context to each cycle
        for cycle in cycles:
            cycle['smoothing_applied'] = getattr(self.edits_smooth_slider, 'value', lambda: 0)() if hasattr(self, 'edits_smooth_slider') else 0
            cycle['baseline_corrected'] = True  # Always applied in processed data
            cycle['export_timestamp'] = datetime.now().isoformat()
            cycle['processing_user'] = self.user_manager.get_current_user() if self.user_manager else 'Unknown'
            cycle['cursor_lock_used'] = getattr(self, '_delta_spr_cursor_locked', False)

        return pd.DataFrame(cycles)
