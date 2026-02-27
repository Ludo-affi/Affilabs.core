"""Alignment & Delta-SPR Mixin for EditsTab.

Contains cycle alignment, time-shift, reference subtraction,
Delta SPR cursor locking, bar-chart update, and processing-cycle creation.
"""

import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import QTableWidgetItem

from affilabs.utils.logger import logger


class AlignmentMixin:
    """Mixin providing alignment, reference subtraction, and Delta SPR logic."""

    # ------------------------------------------------------------------
    # Bar-chart colour updates
    # ------------------------------------------------------------------
    def update_barchart_colors(self, colorblind_enabled: bool = False, hex_colors: list | None = None):
        """Update bar chart and edits graph curve colors from a palette or colorblind toggle.

        Args:
            colorblind_enabled: legacy bool for old colorblind toggle path
            hex_colors: list of 4 hex strings [A, B, C, D] from accessibility panel palette
        """
        if hex_colors is not None:
            bar_colors = hex_colors
        else:
            from affilabs.plot_helpers import CHANNEL_COLORS, CHANNEL_COLORS_COLORBLIND
            bar_colors = CHANNEL_COLORS_COLORBLIND if colorblind_enabled else CHANNEL_COLORS

        # Update delta SPR bar chart
        for bar, color in zip(self.delta_spr_bars, bar_colors):
            bar.setOpts(brush=pg.mkColor(color))

        # Update edits primary graph curves and channel-end labels
        if hasattr(self, 'edits_graph_curves'):
            from affilabs.settings import settings as _settings
            pen_style_val = getattr(_settings, 'ACTIVE_LINE_STYLE', 1)
            from PySide6.QtCore import Qt
            pen_style = Qt.PenStyle(pen_style_val)
            for i, curve in enumerate(self.edits_graph_curves):
                if i < len(bar_colors):
                    curve.setPen(pg.mkPen(color=bar_colors[i], width=2, style=pen_style))
            if hasattr(self, 'edits_graph_curve_labels'):
                for i, label in enumerate(self.edits_graph_curve_labels):
                    if i < len(bar_colors):
                        label.setColor(bar_colors[i])

        # Update A/B/C/D channel toggle buttons above the graph
        if hasattr(self, 'edits_channel_buttons'):
            from affilabs.ui_styles import get_channel_button_style, get_channel_button_ref_style
            ref = getattr(self, '_edits_ref_channel', None)
            for i, ch in enumerate('ABCD'):
                btn = self.edits_channel_buttons.get(ch)
                if btn and i < len(bar_colors):
                    color = bar_colors[i]
                    btn.setProperty("channel_color", color)
                    style_fn = get_channel_button_ref_style if ch == ref else get_channel_button_style
                    btn.setStyleSheet(style_fn(color))

        # Update floating legend colors
        legend = getattr(self, 'edits_spr_legend', None)
        if legend is not None:
            legend.update_colors()

    # ------------------------------------------------------------------
    # Edits channel button — eventFilter + reference handling
    # Mirrors graph_components.py pattern exactly.
    # ------------------------------------------------------------------
    def eventFilter(self, obj, event):
        """Handle events on edits graph and channel buttons.

        - Ctrl+click on A/B/C/D buttons → set/clear reference channel
        - Left/Right arrow on edits_primary_graph → step cycle selection
        - Resize on edits_primary_graph → reposition floating legend
        """
        from PySide6.QtCore import QEvent, Qt

        graph = getattr(self, 'edits_primary_graph', None)

        # ── Graph keyboard navigation ──────────────────────────────────
        if obj is graph and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key in (Qt.Key.Key_Left, Qt.Key.Key_Right):
                legend = getattr(self, 'edits_spr_legend', None)
                if legend is not None:
                    from PySide6.QtWidgets import QApplication
                    fw = QApplication.focusWidget()
                    if fw is legend or (fw is not None and legend.isAncestorOf(fw)):
                        # Legend (or a child of it) has focus — route arrows to channel nav
                        legend.keyPressEvent(event)
                        return True
                if key == Qt.Key.Key_Left:
                    self._step_cycle_selection(-1)
                else:
                    self._step_cycle_selection(1)
                return True

        # ── Legend reposition on graph resize ─────────────────────────
        if obj is graph and event.type() == QEvent.Type.Resize:
            if hasattr(self, '_position_edits_legend'):
                self._position_edits_legend()

        # ── Ctrl+click on channel toggle buttons ──────────────────────
        if (event.type() == QEvent.Type.MouseButtonPress
                and event.button() == Qt.MouseButton.LeftButton
                and event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            ch_letter = obj.property("channel_letter")
            if ch_letter and ch_letter in getattr(self, 'edits_channel_buttons', {}):
                self._on_edits_channel_ref_ctrl_click(ch_letter)
                return True

        return False  # pass event through (EditsTab is not a QObject; no Qt super chain)

    def _step_cycle_selection(self, delta: int) -> None:
        """Move table selection by delta rows (−1 = previous, +1 = next)."""
        table = getattr(self, 'cycle_data_table', None)
        if table is None:
            return
        current = table.currentRow()
        row_count = table.rowCount()
        if row_count == 0:
            return
        if current < 0:
            new_row = 0 if delta > 0 else row_count - 1
        else:
            new_row = max(0, min(row_count - 1, current + delta))
        if new_row != current:
            table.clearSelection()
            table.selectRow(new_row)
            table.scrollToItem(table.item(new_row, 0))

    def _on_edits_channel_ref_ctrl_click(self, ch: str) -> None:
        """Set or clear reference channel on Ctrl+click (does not affect checked state)."""
        current_ref = getattr(self, '_edits_ref_channel', None)
        new_ref = None if ch == current_ref else ch
        self._edits_ref_channel = new_ref
        self._update_edits_channel_ref_styles(new_ref)
        combo_text = {None: "None", "A": "Ch A", "B": "Ch B", "C": "Ch C", "D": "Ch D"}
        ref_str = combo_text.get(new_ref, "None")
        # Persist into _cycle_alignment so _on_cycle_selected_in_table doesn't overwrite it
        row_idx = self.cycle_data_table.currentRow()
        if row_idx >= 0:
            if not hasattr(self.main_window, '_cycle_alignment'):
                self.main_window._cycle_alignment = {}
            if row_idx not in self.main_window._cycle_alignment:
                self.main_window._cycle_alignment[row_idx] = {'channel': 'All', 'shift': 0.0, 'ref': 'Global'}
            self.main_window._cycle_alignment[row_idx]['ref'] = ref_str
        # Sync combo (signals blocked — _cycle_alignment is now the source of truth)
        if hasattr(self, 'alignment_ref_combo'):
            self.alignment_ref_combo.blockSignals(True)
            self.alignment_ref_combo.setCurrentText(ref_str)
            self.alignment_ref_combo.blockSignals(False)
        self._on_reference_changed(ref_str)

    def _update_edits_channel_ref_styles(self, ref_ch: "str | None") -> None:
        """Apply dotted border to the reference channel button; restore others."""
        from affilabs.ui_styles import get_channel_button_style, get_channel_button_ref_style
        for ch, btn in getattr(self, 'edits_channel_buttons', {}).items():
            color = btn.property("channel_color") or "#1D1D1F"
            style_fn = get_channel_button_ref_style if ch == ref_ch else get_channel_button_style
            btn.setStyleSheet(style_fn(color))

    # ------------------------------------------------------------------
    # Alignment channel / shift handlers
    # ------------------------------------------------------------------
    def _on_edits_legend_channel_selected(self, channel: str) -> None:
        """Handle legend row click → select that channel for time-shift (mirrors live-view)."""
        ch_upper = channel.upper()  # 'a' → 'A'
        proxy = getattr(self, 'alignment_channel_combo', None)
        if proxy is not None:
            proxy.setCurrentText(ch_upper)
        # Highlight legend selection
        legend = getattr(self, 'edits_spr_legend', None)
        if legend is not None:
            legend.selected_channel = channel
            for ch_key in ('a', 'b', 'c', 'd'):
                legend._update_channel_appearance(ch_key, ch_key == channel)
        # Trigger graph redraw with the new channel focus
        self._on_alignment_channel_changed(ch_upper)

    def _on_alignment_channel_changed(self, channel):
        """Handle channel change in alignment panel."""
        # Get selected row
        selected_items = self.cycle_data_table.selectedItems()
        if not selected_items:
            return

        row_idx = selected_items[0].row()

        # Update alignment data
        if row_idx not in self._cycle_alignment:
            self._cycle_alignment[row_idx] = {'channel': 'All', 'shift': 0.0}

        self._cycle_alignment[row_idx]['channel'] = channel

        logger.info(f"Cycle {row_idx + 1} channel changed to: {channel}")

        # Trigger graph update
        if hasattr(self.main_window, '_on_cycle_selected_in_table'):
            self.main_window._on_cycle_selected_in_table()

    # ------------------------------------------------------------------
    # Processing cycle creation
    # ------------------------------------------------------------------
    def _create_processing_cycle(self):
        """Create a processing cycle by extracting selected channels from multiple cycles.

        Uses the channel filter settings from the alignment panel to determine which
        channel to extract from each cycle. Concatenates the extracted data into a
        new synthetic cycle for data processing.
        """
        from PySide6.QtWidgets import QInputDialog, QMessageBox
        import pandas as pd
        from pathlib import Path
        from datetime import datetime

        try:
            # Get selected cycles
            selected_rows = sorted(set(item.row() for item in self.cycle_data_table.selectedItems()))

            if not selected_rows:
                QMessageBox.information(
                    self.main_window,
                    "No Selection",
                    "Please select one or more cycles to create a processing cycle."
                )
                return

            # Ask user for cycle name
            cycle_name, ok = QInputDialog.getText(
                self.main_window,
                "Create Processing Cycle",
                "Enter a name for this processing cycle:",
                text=f"Processing_Cycle_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )

            if not ok or not cycle_name:
                return  # User cancelled

            logger.info(f"Creating processing cycle: {cycle_name}")
            logger.info(f"   Extracting from {len(selected_rows)} source cycle(s)")

            # Collect extracted channel data
            combined_data = []
            current_time = 0.0

            metadata = {
                'name': cycle_name,
                'created': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'source_cycles': [],
                'type': 'processing',
                'description': f"Channel-filtered processing cycle from {len(selected_rows)} source(s)"
            }

            WAVELENGTH_TO_RU = 355.0

            for row in selected_rows:
                if row >= len(self.main_window._loaded_cycles_data):
                    continue

                cycle = self.main_window._loaded_cycles_data[row]
                cycle_name_src = cycle.get('name', f'Cycle {row}')
                start_time = cycle.get('start_time_sensorgram', 0.0)
                end_time = cycle.get('end_time_sensorgram', 0.0)

                # Get alignment settings for this cycle (determines which channel to extract)
                alignment = self._cycle_alignment.get(row, {'channel': 'All', 'shift': 0.0})
                channel_filter = alignment.get('channel', 'All')
                time_shift = alignment.get('shift', 0.0)

                logger.info(f"   Cycle {row} ({cycle_name_src}): Extracting channel {channel_filter}, shift={time_shift}s")

                # Record metadata
                metadata['source_cycles'].append({
                    'index': row,
                    'name': cycle_name_src,
                    'channel': channel_filter,
                    'time_shift': time_shift,
                    'duration_s': end_time - start_time
                })

                # Get raw data (list of dicts with 'time', 'channel', 'value')
                raw_data_list = self.main_window._loaded_raw_data
                if not raw_data_list:
                    logger.warning("      No raw data available")
                    continue

                # Filter to cycle time range and extract selected channel(s)
                channels_to_extract = self.CHANNELS_LOWER if channel_filter == 'All' else [channel_filter.lower()]

                points_before = len(combined_data)
                for ch in channels_to_extract:
                    # Extract data for this channel in this time range
                    for row_data in raw_data_list:
                        if row_data.get('channel') == ch:
                            time = row_data.get('time')
                            value = row_data.get('value')

                            if time is not None and value is not None:
                                if start_time <= time <= end_time:
                                    # Normalize time to start at current_time
                                    adjusted_time = time - start_time + time_shift + current_time
                                    combined_data.append({
                                        'Time_s': adjusted_time,
                                        'Channel': ch,
                                        'Response_RU': value
                                    })

                # Update time offset
                cycle_duration = end_time - start_time
                current_time += cycle_duration
                points_extracted = len(combined_data) - points_before

                logger.info(f"      Extracted {points_extracted} time points, total duration now: {current_time:.1f}s")

            if not combined_data:
                QMessageBox.warning(
                    self.main_window,
                    "No Data",
                    "No data was extracted from selected cycles.\n\n"
                    "Check that cycles have valid data and channel filters are set."
                )
                return

            # Save to Excel
            output_dir = Path('data_results/processing_cycles')
            output_dir.mkdir(parents=True, exist_ok=True)

            safe_name = "".join(c for c in cycle_name if c.isalnum() or c in (' ', '-', '_')).strip()
            output_file = output_dir / f"{safe_name}.xlsx"

            # Check if exists
            if output_file.exists():
                reply = QMessageBox.question(
                    self.main_window,
                    "File Exists",
                    f"Processing cycle '{cycle_name}' already exists.\n\nOverwrite?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if reply == QMessageBox.No:
                    return

            # Write Excel file
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                # Sheet 1: Extracted data in long format
                df_data = pd.DataFrame(combined_data)
                df_data.to_excel(writer, sheet_name='Data', index=False)

                # Sheet 2: Metadata
                df_meta = pd.DataFrame([metadata])
                df_meta.to_excel(writer, sheet_name='Metadata', index=False)

                # Sheet 3: Source details
                df_sources = pd.DataFrame(metadata['source_cycles'])
                df_sources.to_excel(writer, sheet_name='Source_Cycles', index=False)

            logger.info(f"Created processing cycle: {cycle_name}")
            logger.info(f"   Total data points: {len(combined_data)}")
            logger.info(f"   Total duration: {current_time:.1f}s")
            logger.info(f"   Saved to: {output_file}")

            QMessageBox.information(
                self.main_window,
                "Processing Cycle Created",
                f"Processing cycle '{cycle_name}' created!\n\n"
                f"Source cycles: {len(selected_rows)}\n"
                f"Data points: {len(combined_data)}\n"
                f"Duration: {current_time/60:.1f} min\n\n"
                f"Saved to:\n{output_file}\n\n"
                f"This file contains only the selected channel(s) from each cycle."
            )

        except Exception as e:
            logger.exception(f"Error creating processing cycle: {e}")
            from PySide6.QtWidgets import QMessageBox as _QMB
            _QMB.critical(
                self.main_window,
                "Processing Cycle Error",
                f"Failed to create processing cycle:\n\n{str(e)}"
            )

    # ------------------------------------------------------------------
    # Delta SPR cursor locking
    # ------------------------------------------------------------------
    def _toggle_delta_spr_lock(self, checked):
        """Toggle Delta SPR cursor locking based on contact_time.

        When locked, cursor distance is maintained at contact_time + 10%.
        """
        if checked:
            # Enable locking - get current cycle's contact_time
            row_idx = self.cycle_data_table.currentRow()
            if row_idx < 0:
                # No cycle selected, disable lock
                self.delta_spr_lock_btn.setChecked(False)
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(
                    self.main_window,
                    "No Cycle Selected",
                    "Please select a cycle to lock cursors to its contact time."
                )
                return

            # Get contact_time from current cycle or from loaded cycles data
            contact_time = None

            # First, check if the selected row is the currently running cycle
            # If so, use the live _current_cycle.contact_time which is already populated
            if (hasattr(self.main_window, '_current_cycle') and
                self.main_window._current_cycle is not None):
                current_cycle = self.main_window._current_cycle
                # Try to match by cycle number (row_idx is 0-based, cycle_num can vary)
                # The selected row should correspond to the current cycle being run
                if hasattr(current_cycle, 'contact_time') and current_cycle.contact_time is not None:
                    contact_time = current_cycle.contact_time
                    logger.debug(f"Using contact_time from live _current_cycle: {contact_time}s")

            # If not found in current cycle, try loaded data
            if contact_time is None and (hasattr(self.main_window, '_loaded_cycles_data') and
                row_idx < len(self.main_window._loaded_cycles_data)):
                cycle = self.main_window._loaded_cycles_data[row_idx]
                contact_time = cycle.get('contact_time')
                if contact_time is not None:
                    logger.debug(f"Using contact_time from loaded_cycles_data: {contact_time}s")

            if contact_time is None or contact_time <= 0:
                # No valid contact_time, disable lock
                self.delta_spr_lock_btn.setChecked(False)
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(
                    self.main_window,
                    "No Contact Time",
                    "Selected cycle has no valid contact time.\n"
                    "Please ensure contact_time is set in the cycle data."
                )
                return

            # Calculate locked distance: contact_time + 10%
            self._delta_spr_lock_distance = float(contact_time) * 1.1
            self._delta_spr_cursor_locked = True

            # Update button appearance
            self.delta_spr_lock_btn.setText(" Lock")
            self.delta_spr_lock_btn.setToolTip(
                f"Cursors locked at contact_time x 1.1 = {self._delta_spr_lock_distance:.1f}s"
            )

            logger.info(f"Delta SPR cursors locked to {self._delta_spr_lock_distance:.1f}s "
                       f"(contact_time={contact_time:.1f}s + 10%)")
        else:
            # Disable locking
            self._delta_spr_cursor_locked = False
            self.delta_spr_lock_btn.setText(" Unlock")
            self.delta_spr_lock_btn.setToolTip(
                "Lock cursors to contact_time + 10% for consistent delta SPR measurement"
            )
            logger.info("Delta SPR cursors unlocked - free movement enabled")

    def _reset_delta_spr_lock(self):
        """Reset Delta SPR lock when a new cycle is selected.

        Unsets the lock button and clears lock state when switching cycles.
        """
        if self._delta_spr_cursor_locked:
            # Uncheck the lock button (will trigger _toggle_delta_spr_lock with checked=False)
            self.delta_spr_lock_btn.blockSignals(True)
            self.delta_spr_lock_btn.setChecked(False)
            self.delta_spr_lock_btn.blockSignals(False)

            # Call the toggle handler to update state and button text
            self._toggle_delta_spr_lock(False)

    def _enforce_delta_spr_lock(self):
        """Enforce cursor distance constraint when locked to contact_time + 10%.

        If cursors are locked, maintains the distance between them.
        Uses the start cursor as anchor and adjusts the stop cursor.
        """
        if not self._delta_spr_cursor_locked or self._suppressing_position_change:
            return

        # Get current positions
        start_time = self.delta_spr_start_cursor.value()
        stop_time = self.delta_spr_stop_cursor.value()
        current_distance = abs(stop_time - start_time)

        # Check which cursor moved more recently (heuristic: stop cursor is usually adjusted last)
        # If the actual distance doesn't match the locked distance, enforce it
        target_distance = self._delta_spr_lock_distance

        if abs(current_distance - target_distance) > 0.1:  # Allow small tolerance
            # Mark that we're adjusting position to prevent recursive updates
            self._suppressing_position_change = True
            try:
                # Adjust stop cursor to maintain locked distance
                new_stop = start_time + target_distance
                self.delta_spr_stop_cursor.setValue(new_stop)
            finally:
                self._suppressing_position_change = False

    # ------------------------------------------------------------------
    # Delta SPR bar-chart update
    # ------------------------------------------------------------------
    def _update_delta_spr_barchart(self):
        """Update Delta SPR bar chart based on cursor positions."""
        if not hasattr(self, 'delta_spr_bars'):
            return

        # Enforce lock constraint if enabled
        self._enforce_delta_spr_lock()

        start_time = self.delta_spr_start_cursor.value()
        stop_time = self.delta_spr_stop_cursor.value()

        # Ensure start is before stop
        if start_time > stop_time:
            start_time, stop_time = stop_time, start_time

        # Calculate Delta SPR for each channel between cursors
        self.current_delta_values = []  # Store for saving later
        for ch_idx, curve in enumerate(self.edits_graph_curves):
            data = curve.getData()
            if data[0] is None or len(data[0]) == 0:
                self.current_delta_values.append(0)
                continue

            times, values = data

            # Find closest point to start cursor
            start_mask = times >= start_time
            if start_mask.sum() > 0:
                start_idx = np.where(start_mask)[0][0]
                start_value = values[start_idx]
            else:
                self.current_delta_values.append(0)
                continue

            # Find closest point to stop cursor
            stop_mask = times <= stop_time
            if stop_mask.sum() > 0:
                stop_idx = np.where(stop_mask)[0][-1]
                stop_value = values[stop_idx]
            else:
                self.current_delta_values.append(0)
                continue

            # Delta SPR = end value - start value (actual response)
            delta_spr = stop_value - start_value
            self.current_delta_values.append(delta_spr)

        # Update bar heights and value labels
        for i, (bar, delta_val) in enumerate(zip(self.delta_spr_bars, self.current_delta_values)):
            bar.setOpts(height=[delta_val])

            # Update value label position and text
            if hasattr(self, 'delta_spr_labels') and i < len(self.delta_spr_labels):
                label = self.delta_spr_labels[i]
                label.setText(f"{delta_val:.1f}")
                # Position label above bar (with more space) or below if negative
                # Add fixed offset to prevent cutoff
                if delta_val >= 0:
                    label_offset = max(abs(delta_val) * 0.08, 15)  # At least 15 RU above bar
                    label_y = delta_val + label_offset
                else:
                    label_offset = max(abs(delta_val) * 0.08, 15)  # At least 15 RU below bar
                    label_y = delta_val - label_offset
                label.setPos(i, label_y)

        # Auto-scale Y axis (handle negative values too)
        if self.current_delta_values:
            min_delta = min(self.current_delta_values)
            max_delta = max(self.current_delta_values)
            y_range = max_delta - min_delta
            # Increase padding significantly to accommodate labels (25% on each side)
            padding = max(y_range * 0.25, 50)  # At least 50 RU padding for label space
            self.delta_spr_barchart.setYRange(min_delta - padding, max_delta + padding)
        else:
            self.delta_spr_barchart.setYRange(0, 100)

        # Auto-save delta SPR to the currently selected cycle
        row_idx = self.cycle_data_table.currentRow()
        if (row_idx >= 0
                and hasattr(self.main_window, '_loaded_cycles_data')
                and row_idx < len(self.main_window._loaded_cycles_data)):
            cycle = self.main_window._loaded_cycles_data[row_idx]
            ch_labels = self.CHANNELS
            delta_parts = []
            for ch_idx, delta_val in enumerate(self.current_delta_values):
                cycle[f'delta_ch{ch_idx + 1}'] = round(delta_val, 2)
                delta_parts.append(f"{ch_labels[ch_idx]}:{delta_val:.0f}")
            # Update ΔSPR column in the table (col 4 — last column)
            delta_str = " ".join(delta_parts)
            self.cycle_data_table.setItem(row_idx, self.TABLE_COL_DELTA_SPR, QTableWidgetItem(delta_str))
            # Store reference channel and measurement flag for binding plot (Option A)
            ref_ch = self._get_effective_ref_channel(row_idx)
            cycle['delta_ref_ch'] = f'Ch {chr(65 + ref_ch)}' if ref_ch is not None else 'None'
            cycle['delta_measured'] = True
            # Propagate to binding plot if visible
            if hasattr(self, 'bottom_tab_widget') and self.bottom_tab_widget.currentIndex() == 1:
                self._update_binding_plot()

        # ── Update floating legend ─────────────────────────────────────
        legend = getattr(self, 'edits_spr_legend', None)
        if legend is not None and self.current_delta_values:
            ch_keys = ['a', 'b', 'c', 'd']
            legend.update_values({
                ch: float(v)
                for ch, v in zip(ch_keys, self.current_delta_values)
            })
            if not legend.isVisible():
                legend.setVisible(True)
                self._position_edits_legend()

    # ------------------------------------------------------------------
    # Time-shift application & slider/input sync
    # ------------------------------------------------------------------
    def _apply_time_shift(self):
        """Apply time shift to the selected cycle's sensorgram."""
        from PySide6.QtWidgets import QMessageBox

        # Check if a cycle is selected
        selected_rows = self.cycle_data_table.selectedItems()
        if not selected_rows:
            QMessageBox.warning(
                self.main_window,
                "No Cycle Selected",
                "Please select a cycle in the table to apply time shift."
            )
            return

        # Get the selected row index
        row_idx = self.cycle_data_table.currentRow()
        if row_idx < 0:
            return

        # Get shift value
        try:
            shift_value = float(self.alignment_shift_input.text())
        except ValueError:
            QMessageBox.warning(
                self.main_window,
                "Invalid Input",
                "Please enter a valid number for time shift (in seconds)."
            )
            return

        # Get selected channel
        channel_text = self.alignment_channel_combo.currentText()
        channel_map = {"All": None, "A": 0, "B": 1, "C": 2, "D": 3}
        channel_idx = channel_map.get(channel_text)

        # Update the cycle data with shift
        if hasattr(self.main_window, '_loaded_cycles_data') and row_idx < len(self.main_window._loaded_cycles_data):
            cycle = self.main_window._loaded_cycles_data[row_idx]

            # Store the shift in the cycle data
            if 'shifts' not in cycle:
                cycle['shifts'] = {}

            if channel_idx is None:
                # Apply to all channels
                for ch in range(4):
                    cycle['shifts'][ch] = shift_value
                cycle['shift'] = shift_value  # Also update main shift field
            else:
                # Apply to specific channel
                cycle['shifts'][channel_idx] = shift_value

            # Table display -- shift is no longer a visible column

            # Initialize _cycle_alignment if it doesn't exist
            if not hasattr(self.main_window, '_cycle_alignment'):
                self.main_window._cycle_alignment = {}

            # Update the _cycle_alignment dictionary that the graph uses
            ref_text = self.alignment_ref_combo.currentText() if hasattr(self, 'alignment_ref_combo') else 'Global'
            self.main_window._cycle_alignment[row_idx] = {
                'channel': channel_text,
                'shift': shift_value,
                'ref': ref_text,
            }

            # Refresh the graph with shifted data
            if hasattr(self, 'edits_graph_curves'):
                # Re-select the cycle to refresh the display with shift
                self.main_window._on_cycle_selected_in_table()

            logger.info(f"Applied {shift_value}s time shift to cycle {row_idx + 1}, channel {channel_text}")
        else:
            from PySide6.QtWidgets import QMessageBox as _QMB
            _QMB.warning(
                self.main_window,
                "Error",
                "Could not access cycle data. Please reload the data."
            )

    def _on_shift_input_changed(self, text):
        """Sync slider when input box changes."""
        try:
            shift_value = float(text)
            # Clamp to slider range
            shift_value = max(-20.0, min(20.0, shift_value))
            slider_value = int(shift_value * 10)  # Convert to 0.1s increments
            self.alignment_shift_slider.blockSignals(True)
            self.alignment_shift_slider.setValue(slider_value)
            self.alignment_shift_slider.blockSignals(False)
        except ValueError:
            pass  # Ignore invalid input

    def _on_shift_slider_changed(self, value):
        """Sync input box when slider changes and apply shift in real-time."""
        shift_value = value / 10.0  # Convert from 0.1s increments to seconds
        self.alignment_shift_input.blockSignals(True)
        self.alignment_shift_input.setText(f"{shift_value:.1f}")
        self.alignment_shift_input.blockSignals(False)

        # Apply shift in real-time (no need to press button)
        self._apply_time_shift()

    # ------------------------------------------------------------------
    # Reference subtraction
    # ------------------------------------------------------------------
    def _on_reference_changed(self, text):
        """Handle global reference channel change -- refresh graph with subtraction."""
        # Refresh graph to apply/remove reference subtraction
        if hasattr(self.main_window, '_on_cycle_selected_in_table'):
            self.main_window._on_cycle_selected_in_table()

    def _get_effective_ref_channel(self, row_idx):
        """Get the effective reference channel for a cycle.

        Returns channel index (0-3) or None.
        Per-cycle override takes priority over global toolbar setting.
        """
        _REF_MAP = {"None": None, "Ch A": 0, "Ch B": 1, "Ch C": 2, "Ch D": 3}

        # Check per-cycle override
        if hasattr(self.main_window, '_cycle_alignment'):
            per_cycle_ref = self.main_window._cycle_alignment.get(row_idx, {}).get('ref', 'Global')
        else:
            per_cycle_ref = 'Global'

        if per_cycle_ref != 'Global':
            return _REF_MAP.get(per_cycle_ref)

        # Fall back to global toolbar Ref
        if hasattr(self, 'alignment_ref_combo'):
            return _REF_MAP.get(self.alignment_ref_combo.currentText())
        return None

    def _on_cycle_ref_changed(self, text):
        """Handle per-cycle reference channel change -- save and refresh graph."""
        row_idx = self.cycle_data_table.currentRow()
        if row_idx < 0:
            return

        if not hasattr(self.main_window, '_cycle_alignment'):
            self.main_window._cycle_alignment = {}

        if row_idx not in self.main_window._cycle_alignment:
            self.main_window._cycle_alignment[row_idx] = {'channel': 'All', 'shift': 0.0, 'ref': 'Global'}

        self.main_window._cycle_alignment[row_idx]['ref'] = text

        # Refresh graph
        if hasattr(self.main_window, '_on_cycle_selected_in_table'):
            self.main_window._on_cycle_selected_in_table()
