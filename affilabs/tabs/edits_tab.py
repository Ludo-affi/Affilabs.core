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

from affilabs.utils.logger import logger
from affilabs.tabs.edits._data_mixin import DataMixin
from affilabs.tabs.edits._export_mixin import ExportMixin
from affilabs.tabs.edits._ui_builders import UIBuildersMixin
from affilabs.tabs.edits._alignment_mixin import AlignmentMixin
from affilabs.tabs.edits._table_mixin import TableMixin


class EditsTab(DataMixin, ExportMixin, UIBuildersMixin, AlignmentMixin, TableMixin):
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

        # DEVICE: Prefer loaded metadata, fall back to current device
        device_str = None

        if loaded_metadata and 'device_id' in loaded_metadata:
            device_str = loaded_metadata['device_id']
        elif hasattr(self.main_window, 'device_config') and self.main_window.device_config:
            dc = self.main_window.device_config
            device_id = getattr(dc, 'device_serial', '') or ''
            device_str = device_id if device_id else None

        self.meta_device.setText(device_str if device_str else "-")

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
