"""Table Operations Mixin for EditsTab.

Contains cycle table management, filtering, context menus,
column visibility, data loading/saving, and cycle editing.
"""

import pyqtgraph as pg
import pandas as pd
from pathlib import Path
from PySide6.QtWidgets import QTableWidgetItem
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor

from affilabs.utils.logger import logger
from affilabs.widgets.ui_constants import CycleTypeStyle
from affilabs.ui_styles import Colors, Fonts


class TableMixin:
    """Mixin providing table management and cycle editing for EditsTab."""

    def _toggle_channel(self, ch_idx, visible):
        """Toggle channel visibility in both graphs and bar chart."""
        if self.edits_timeline_curves:
            self.edits_timeline_curves[ch_idx].setVisible(visible)
        if self.edits_graph_curves:
            self.edits_graph_curves[ch_idx].setVisible(visible)
        # Hide/show corresponding bar and label in delta SPR bar chart
        if hasattr(self, 'delta_spr_bars') and ch_idx < len(self.delta_spr_bars):
            self.delta_spr_bars[ch_idx].setVisible(visible)
        if hasattr(self, 'delta_spr_labels') and ch_idx < len(self.delta_spr_labels):
            self.delta_spr_labels[ch_idx].setVisible(visible)

    def _update_cycle_type_filter(self, cycles_data):
        """Update filter dropdown to show actual cycle types from loaded data."""
        # Extract unique cycle types
        unique_types = set()
        for cycle in cycles_data:
            cycle_type = cycle.get('type', 'Custom')
            unique_types.add(cycle_type)

        # Convert set to sorted list
        sorted_types = sorted(list(unique_types))

        # Disconnect signal temporarily to avoid triggering filter while updating
        self.filter_combo.currentTextChanged.disconnect(self._apply_cycle_filter)

        # Clear and repopulate dropdown
        self.filter_combo.clear()
        self.filter_combo.addItem("All")  # Always include "All"
        for cycle_type in sorted_types:
            self.filter_combo.addItem(cycle_type)

        # Always default to "All" — users scan the full list before narrowing
        self.filter_combo.setCurrentText("All")

        # Reconnect signal
        self.filter_combo.currentTextChanged.connect(self._apply_cycle_filter)

    def _populate_cycles_table(self, cycles_data):
        """Populate the cycles table with loaded cycle data with export selection checkboxes."""
        self.cycle_data_table.setRowCount(0)  # Clear existing rows
        self._cycle_export_selection = {}  # Reset selection tracking
        self._cycle_type_counts = {}  # Reset live type counter (for add_cycle)

        type_counts = {}  # Track numbering per type

        # Update filter dropdown with actual cycle types from loaded data
        self._update_cycle_type_filter(cycles_data)

        for cycle_idx, cycle in enumerate(cycles_data):
            row_idx = self.cycle_data_table.rowCount()
            self.cycle_data_table.insertRow(row_idx)

            # --- Col 0: Export checkbox (proper centered QCheckBox widget) ---
            self.cycle_data_table.setCellWidget(row_idx, 0, self._create_export_checkbox(cycle_idx, checked=True))
            self._cycle_export_selection[cycle_idx] = True

            # --- Col 1: Type icon (color-coded abbreviation) ---
            cycle_type = str(cycle.get('type', 'Custom'))
            type_counts[cycle_type] = type_counts.get(cycle_type, 0) + 1
            abbr, color = CycleTypeStyle.get(cycle_type)
            type_item = QTableWidgetItem(f"{abbr} {type_counts[cycle_type]}")
            type_item.setForeground(QColor(color))
            type_item.setToolTip(f"{cycle_type} {type_counts[cycle_type]}")
            self.cycle_data_table.setItem(row_idx, self.TABLE_COL_TYPE, type_item)

            # --- Col 2: Time (ACTUAL duration @ start) ---
            # Calculate ACTUAL duration (not planned)
            actual_duration_min = self._calculate_actual_duration(cycle_idx, cycle, cycles_data)
            start_time = cycle.get('start_time_sensorgram', 0)

            # Handle NaN values robustly
            dur_valid = pd.notna(actual_duration_min) and isinstance(actual_duration_min, (int, float))
            st_valid = pd.notna(start_time) and isinstance(start_time, (int, float))
            if dur_valid and st_valid:
                time_str = f"{actual_duration_min:.1f}m @ {start_time:.0f}s"
            elif dur_valid:
                time_str = f"{actual_duration_min:.1f}m"
            elif st_valid and start_time != 0:
                time_str = f"@ {start_time:.0f}s"
            else:
                time_str = "—"
            self.cycle_data_table.setItem(row_idx, self.TABLE_COL_TIME, QTableWidgetItem(time_str))

            # --- Col 3: Concentration ---
            conc_val = cycle.get('concentration_value', '')
            conc_str = str(conc_val) if pd.notna(conc_val) and conc_val != '' else ''
            self.cycle_data_table.setItem(row_idx, self.TABLE_COL_CONC, QTableWidgetItem(conc_str))

            # --- Col 4: ΔSPR (combined 4 channels) ---
            delta_parts = []
            for ch_key, ch_label in [('delta_ch1', 'A'), ('delta_ch2', 'B'), ('delta_ch3', 'C'), ('delta_ch4', 'D')]:
                val = cycle.get(ch_key, '')
                if pd.notna(val) and isinstance(val, (int, float)):
                    delta_parts.append(f"{ch_label}:{val:.0f}")
                elif val and pd.notna(val):
                    delta_parts.append(f"{ch_label}:{val}")
            # Also check delta_spr_by_channel dict
            if not delta_parts:
                delta_by_ch = self._parse_delta_spr(cycle)
                for ch in self.CHANNELS:
                    val = delta_by_ch.get(ch, '')
                    if pd.notna(val) and isinstance(val, (int, float)):
                        delta_parts.append(f"{ch}:{val:.0f}")
            delta_str = " ".join(delta_parts) if delta_parts else ''
            self.cycle_data_table.setItem(row_idx, self.TABLE_COL_DELTA_SPR, QTableWidgetItem(delta_str))

        # Update empty state visibility
        self._update_empty_state()

        # Update metadata stats
        if hasattr(self, '_update_metadata_stats'):
            self._update_metadata_stats()

        # Auto-select first row so graph is populated immediately on load
        if self.cycle_data_table.rowCount() > 0:
            QTimer.singleShot(0, lambda: self._select_cycle_by_index(0))

    def _create_export_checkbox(self, cycle_idx: int, checked: bool = True):
        """Create a centered QCheckBox widget for the export column.

        Returns a container QWidget with the checkbox centered inside it.
        """
        from PySide6.QtWidgets import QCheckBox, QWidget, QHBoxLayout

        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(0, 0, 0, 0)

        cb = QCheckBox()
        cb.setChecked(checked)
        cb.setToolTip("Include in export")
        cb.setStyleSheet(
            "QCheckBox::indicator { width: 15px; height: 15px; }"
        )
        cb.stateChanged.connect(lambda state, idx=cycle_idx: self._on_export_checkbox_toggled(idx, state))
        layout.addWidget(cb)
        return container

    def _on_export_checkbox_toggled(self, cycle_idx: int, state: int):
        """Track export checkbox state changes."""
        self._cycle_export_selection[cycle_idx] = (state == Qt.CheckState.Checked.value)

    def _update_cycle_table_row(self, row_idx, cycle):
        """Update a single row in the cycle table.

        Column layout (5 columns): Export(0), Type(1), Time(2), Conc.(3), ΔSPR(4)
        """
        # Col 1: Type icon
        cycle_type = cycle.get('type', 'Custom')
        cycle_num = cycle.get('cycle_number', row_idx + 1)
        abbr, color = CycleTypeStyle.get(cycle_type)
        type_item = QTableWidgetItem(f"{abbr} {cycle_num}")
        type_item.setForeground(QColor(color))
        type_item.setToolTip(f"{cycle_type} {cycle_num}")
        self.cycle_data_table.setItem(row_idx, self.TABLE_COL_TYPE, type_item)

        # Col 2: Time (ACTUAL duration @ start)
        # Get all cycles to calculate actual duration from spacing if needed
        all_cycles = getattr(self.main_window, '_loaded_cycles_data', [])
        if all_cycles:
            actual_duration = self._calculate_actual_duration(row_idx, cycle, all_cycles)
        else:
            # Fallback if no loaded cycles (shouldn't happen in normal operation)
            actual_duration = cycle.get('duration_minutes', '')

        start = cycle.get('start_time_sensorgram', 0)
        if isinstance(actual_duration, (int, float)) and isinstance(start, (int, float)):
            self.cycle_data_table.setItem(row_idx, self.TABLE_COL_TIME, QTableWidgetItem(f"{actual_duration:.1f}m @ {start:.0f}s"))
        else:
            self.cycle_data_table.setItem(row_idx, self.TABLE_COL_TIME, QTableWidgetItem(f"{actual_duration}m @ {start}s"))

        # Col 3: Concentration
        self.cycle_data_table.setItem(row_idx, self.TABLE_COL_CONC, QTableWidgetItem(str(cycle.get('concentration_value', ''))))

        # Col 4: ΔSPR (combined)
        delta_by_ch = self._parse_delta_spr(cycle)
        parts = []
        if delta_by_ch and isinstance(delta_by_ch, dict):
            for ch in self.CHANNELS:
                val = delta_by_ch.get(ch, '')
                if isinstance(val, (int, float)):
                    parts.append(f"{ch}:{val:.0f}")
        if not parts:
            # Fallback: check delta_ch1-delta_ch4 keys
            for ch_key, ch_label in [('delta_ch1', 'A'), ('delta_ch2', 'B'), ('delta_ch3', 'C'), ('delta_ch4', 'D')]:
                val = cycle.get(ch_key, '')
                if isinstance(val, (int, float)):
                    parts.append(f"{ch_label}:{val:.0f}")
        self.cycle_data_table.setItem(row_idx, self.TABLE_COL_DELTA_SPR, QTableWidgetItem(" ".join(parts)))

    def _prefill_delta_spr_from_stats(self, cycle_dict: dict) -> None:
        """Pre-fill delta_ch{n} in cycle_dict from _injection_stats if not already set.

        Writes delta_spr_ru per channel as delta_ch1…delta_ch4 so the binding
        plot can populate automatically without the user placing cursors.
        Also sets delta_measured=True and delta_ref_ch='None' (no reference subtraction
        applied — baseline-to-baseline value from live stats).

        Called from add_cycle() before appending to _loaded_cycles_data.
        """
        inj_stats = getattr(self.main_window, '_injection_stats', {})
        if not inj_stats:
            return

        cycle_num = cycle_dict.get('cycle_num')
        if cycle_num is None:
            return

        _CH_MAP = {'a': 1, 'b': 2, 'c': 3, 'd': 4}
        any_prefilled = False

        for ch, ch_idx in _CH_MAP.items():
            key = (cycle_num, ch)
            entry = inj_stats.get(key)
            if entry is None:
                continue
            delta_ru = entry.get('delta_spr_ru')
            if delta_ru is None:
                continue
            col = f'delta_ch{ch_idx}'
            # Only write if not already set by cursor placement
            if cycle_dict.get(col) is None:
                cycle_dict[col] = round(float(delta_ru), 2)
                any_prefilled = True

        if any_prefilled:
            # Mark as measured (baseline-to-baseline, no cursor reference)
            cycle_dict.setdefault('delta_measured', True)
            cycle_dict.setdefault('delta_ref_ch', 'None')
            # Also auto-fill immob_delta_spr_ru for Rmax calculator
            ctype = cycle_dict.get('type', '')
            if ctype in ('Immobilisation', 'Immobilization'):
                # Average across channels that have a value
                vals = [
                    cycle_dict[f'delta_ch{i}']
                    for i in range(1, 5)
                    if isinstance(cycle_dict.get(f'delta_ch{i}'), (int, float))
                ]
                if vals:
                    self._immob_delta_spr_ru = abs(sum(vals) / len(vals))
                    if hasattr(self, 'rmax_immob_lbl'):
                        self.rmax_immob_lbl.setText(f"{self._immob_delta_spr_ru:.0f} RU")
            logger.debug(
                f"[Edits] Auto-prefilled ΔSPR from live stats for cycle {cycle_num}"
            )

    def add_cycle(self, cycle_dict):
        """Add a single completed cycle to the table (public API called by main.py).

        Called when a cycle completes during live acquisition.
        This should be called when a cycle completes, not when cycles are queued.

        Args:
            cycle_dict: Dictionary from Cycle.to_export_dict() containing cycle data
        """
        # Get current row count (where we'll add the new row)
        row_idx = self.cycle_data_table.rowCount()
        self.cycle_data_table.insertRow(row_idx)

        # Initialize or get loaded cycles data list
        if not hasattr(self.main_window, '_loaded_cycles_data'):
            self.main_window._loaded_cycles_data = []

        # Auto-prefill delta_ch{n} from live binding stats if available (§11 of FRS)
        self._prefill_delta_spr_from_stats(cycle_dict)

        self.main_window._loaded_cycles_data.append(cycle_dict)

        # Count cycle type for numbering
        if not hasattr(self, '_cycle_type_counts'):
            self._cycle_type_counts = {}

        cycle_type = cycle_dict.get('type', 'Custom')
        if cycle_type not in self._cycle_type_counts:
            self._cycle_type_counts[cycle_type] = 0
        self._cycle_type_counts[cycle_type] += 1
        cycle_num = self._cycle_type_counts[cycle_type]

        # Col 0: Export checkbox (proper centered QCheckBox widget)
        self.cycle_data_table.setCellWidget(row_idx, 0, self._create_export_checkbox(row_idx, checked=True))
        self._cycle_export_selection[row_idx] = True

        # Col 1: Type icon + number
        abbr, color = CycleTypeStyle.get(cycle_type)
        type_item = QTableWidgetItem(f"{abbr} {cycle_num}")
        type_item.setForeground(QColor(color))
        type_item.setToolTip(f"{cycle_type} {cycle_num}")
        self.cycle_data_table.setItem(row_idx, self.TABLE_COL_TYPE, type_item)

        # Col 2: Time (duration @ start)
        duration = cycle_dict.get('duration_minutes', '')
        start = cycle_dict.get('start_time_sensorgram', 0)
        if isinstance(duration, (int, float)) and isinstance(start, (int, float)):
            self.cycle_data_table.setItem(row_idx, self.TABLE_COL_TIME, QTableWidgetItem(f"{duration:.1f}m @ {start:.0f}s"))
        else:
            self.cycle_data_table.setItem(row_idx, self.TABLE_COL_TIME, QTableWidgetItem(f"{duration}m @ {start}s"))

        # Col 3: Concentration
        conc_value = cycle_dict.get('concentration_value', '')
        self.cycle_data_table.setItem(row_idx, self.TABLE_COL_CONC, QTableWidgetItem(str(conc_value)))

        # Col 4: ΔSPR (combined 4 channels)
        # Priority 1: delta_spr_by_channel dict (live acquisition format)
        delta_by_ch = self._parse_delta_spr(cycle_dict)
        parts = []
        if delta_by_ch and isinstance(delta_by_ch, dict):
            for ch in self.CHANNELS:
                val = delta_by_ch.get(ch, '')
                if isinstance(val, (int, float)):
                    parts.append(f"{ch}:{val:.0f}")
        # Priority 2: delta_ch1-4 keys (Excel import fallback)
        if not parts:
            for ch_key, ch_label in [('delta_ch1', 'A'), ('delta_ch2', 'B'), ('delta_ch3', 'C'), ('delta_ch4', 'D')]:
                val = cycle_dict.get(ch_key, '')
                if isinstance(val, (int, float)):
                    parts.append(f"{ch_label}:{val:.0f}")
        self.cycle_data_table.setItem(row_idx, self.TABLE_COL_DELTA_SPR, QTableWidgetItem(" ".join(parts)))

        # Store flags and notes in cycle details dict for details panel (not shown in table)
        if not hasattr(self, '_cycle_details_data'):
            self._cycle_details_data = {}

        flags_display = self._format_flags_display(cycle_dict)

        notes = cycle_dict.get('note', '')
        cycle_id = cycle_dict.get('cycle_id', '')

        self._cycle_details_data[row_idx] = {
            'flags': flags_display,
            'note': notes,
            'cycle_id': cycle_id
        }

        # Update UI state and metadata
        self._update_empty_state()
        if hasattr(self, '_update_metadata_stats'):
            self._update_metadata_stats()
        
        # Update filter dropdown if new cycle type encountered
        if hasattr(self, 'filter_combo'):
            current_types = [self.filter_combo.itemText(i) for i in range(self.filter_combo.count())]
            if cycle_type not in current_types:
                self.filter_combo.addItem(cycle_type)
        
        # Auto-scroll to show newest cycle
        self.cycle_data_table.scrollToBottom()

        logger.info(f"✓ Added {cycle_type} {cycle_num} to cycle table (row {row_idx + 1})")

    def _select_cycle_by_index(self, cycle_idx):
        """Select a cycle by index and move cursors to its bounds.

        Args:
            cycle_idx: Index of the cycle to select
        """
        # Select the corresponding row in the table
        self.cycle_data_table.clearSelection()
        self.cycle_data_table.selectRow(cycle_idx)

        logger.info(f"✓ Clicked cycle marker {cycle_idx + 1}")

        # The table selection change will trigger _on_cycle_selected_in_table
        # which updates the cursors and graph

    def add_cycle_markers_to_timeline(self, cycles_data):
        """Add colored background regions and labels for each cycle.

        Args:
            cycles_data: List of cycle dictionaries with start/end times and type
        """
        from affilabs.utils.logger import logger

        # Clear existing markers
        for marker in self.edits_cycle_markers:
            self.edits_timeline_graph.removeItem(marker)
        for label in self.edits_cycle_labels:
            self.edits_timeline_graph.removeItem(label)

        self.edits_cycle_markers = []
        self.edits_cycle_labels = []

        # Color scheme by cycle type (R, G, B, Alpha)
        # Increased alpha from 40 to 120 for better visibility
        cycle_colors = {
            'baseline': (200, 200, 200, 120),      # Light gray
            'association': (100, 150, 255, 120),   # Light blue
            'dissociation': (255, 255, 150, 120),  # Light yellow
            'regeneration': (255, 150, 150, 120),  # Light red
            'wash': (150, 255, 200, 120),          # Light green
            'concentration': (150, 200, 255, 120), # Light cyan
            'conc.': (150, 200, 255, 120),         # Light cyan
            'default': (220, 220, 220, 100),       # Very light gray
        }

        for idx, cycle in enumerate(cycles_data):
            start = cycle.get('start_time_sensorgram', cycle.get('sensorgram_time', 0))
            end = cycle.get('end_time_sensorgram', start + 100)
            cycle_type = cycle.get('type', '').lower()
            # Use index-based numbering instead of data name (fixes duplicate labeling)
            name = f'Cycle {idx+1}'

            # Get color for this cycle type
            color = cycle_colors.get(cycle_type, cycle_colors['default'])

            # Create filled region for cycle background
            region = pg.LinearRegionItem(
                values=(start, end),
                orientation='vertical',
                brush=pg.mkBrush(*color),
                movable=False
            )
            region.setZValue(-10)  # Put behind data curves

            # Store cycle index for mouse event handler
            region.cycle_index = idx

            # Override mouse click to select cycle
            def make_click_handler(cycle_idx):
                def mouseClickEvent(event):
                    if event.button() == Qt.LeftButton:
                        self._select_cycle_by_index(cycle_idx)
                        event.accept()
                return mouseClickEvent

            region.mouseClickEvent = make_click_handler(idx)

            self.edits_timeline_graph.addItem(region)
            self.edits_cycle_markers.append(region)

            # Add boundary line at start
            line = pg.InfiniteLine(
                pos=start, angle=90, movable=False,
                pen=pg.mkPen((120, 120, 120), width=2, style=Qt.DotLine)
            )
            self.edits_timeline_graph.addItem(line)
            self.edits_cycle_markers.append(line)

            # Add label with cycle name and type
            label_text = f"{name}"
            if cycle_type and cycle_type not in name.lower():
                label_text = f"{name}\n({cycle_type})"

            label = pg.TextItem(
                text=label_text,
                color=(60, 60, 60),
                anchor=(0, 0.5),  # Left-center anchor for better visibility
                fill=pg.mkBrush(255, 255, 255, 220),
                border=pg.mkPen((180, 180, 180), width=1)
            )
            # Position label at start + small offset, centered vertically
            label.setPos(start + 2, 0)
            self.edits_timeline_graph.addItem(label)
            self.edits_cycle_labels.append(label)

        logger.info(f"✓ Added {len(cycles_data)} cycle markers with colored backgrounds to timeline")

    def _on_table_context_menu(self, position):
        """Show context menu for cycle table with option to load to reference graphs or delete."""
        from PySide6.QtWidgets import QMenu

        menu = QMenu()

        # Get selected rows
        selected_rows = sorted(set(item.row() for item in self.cycle_data_table.selectedItems()))

        if not selected_rows:
            return  # No selection, don't show menu

        if len(selected_rows) == 1:
            # Single cycle selected - offer to edit timing
            edit_action = menu.addAction("✏️ Edit Cycle Timing")
            edit_action.triggered.connect(lambda: self._edit_cycle_timing(selected_rows[0]))

            menu.addSeparator()

            # Single cycle selected - offer to load to reference slots
            ref_menu = menu.addMenu("📊 Load to Reference Graph")

            for i in range(3):
                ref_label = f"Reference {i + 1}"
                # Check if slot is already occupied
                if hasattr(self.main_window, 'edits_reference_cycle_data'):
                    existing_cycle = self.main_window.edits_reference_cycle_data[i]
                    if existing_cycle is not None:
                        ref_label += f" (Currently: Cycle {existing_cycle + 1})"

                action = ref_menu.addAction(ref_label)
                action.triggered.connect(lambda checked=False, row=selected_rows[0], idx=i:
                                        self.main_window._load_cycle_to_reference(row, idx))

            menu.addSeparator()

        # Delete option (works for single or multiple selections)
        if len(selected_rows) == 1:
            cycle_text = "this cycle"
        else:
            cycle_text = f"{len(selected_rows)} cycles"

        delete_action = menu.addAction(f"🗑️ Delete {cycle_text}")
        delete_action.triggered.connect(lambda: self._delete_cycles_from_table(selected_rows))

        # Show menu at cursor position
        menu.exec(self.cycle_data_table.viewport().mapToGlobal(position))

    def _delete_cycles_from_table(self, row_indices):
        """Delete selected cycles from the cycle data table.

        Args:
            row_indices: List of row indices to delete
        """
        from PySide6.QtWidgets import QMessageBox
        from affilabs.utils.logger import logger

        if not row_indices:
            return

        # Confirm deletion
        if len(row_indices) == 1:
            msg = "Are you sure you want to delete this cycle?"
        else:
            msg = f"Are you sure you want to delete {len(row_indices)} cycles?"

        reply = QMessageBox.question(
            self.main_window,
            "Delete Cycle(s)",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Delete from table and data (reverse order to maintain indices)
        for row in sorted(row_indices, reverse=True):
            # Remove from loaded cycles data if it exists
            if hasattr(self.main_window, '_loaded_cycles_data') and row < len(self.main_window._loaded_cycles_data):
                del self.main_window._loaded_cycles_data[row]

            # Remove from cycle alignment settings
            if hasattr(self.main_window, '_cycle_alignment') and row in self.main_window._cycle_alignment:
                del self.main_window._cycle_alignment[row]

            # Remove row from table
            self.cycle_data_table.removeRow(row)

        # Rebuild cycle alignment indices (they shifted after deletion)
        if hasattr(self.main_window, '_cycle_alignment'):
            new_alignment = {}
            for old_idx, settings in sorted(self.main_window._cycle_alignment.items()):
                # Calculate how many deletions occurred before this index
                shift = sum(1 for deleted_row in row_indices if deleted_row < old_idx)
                new_idx = old_idx - shift
                new_alignment[new_idx] = settings
            self.main_window._cycle_alignment = new_alignment

        logger.info(f"🗑️ Deleted {len(row_indices)} cycle(s) from data table")

        # Show confirmation
        if hasattr(self.main_window, 'sidebar') and hasattr(self.main_window.sidebar, 'intel_message_label'):
            self.main_window.sidebar.intel_message_label.setText(
                f"🗑️ Deleted {len(row_indices)} cycle{'s' if len(row_indices) > 1 else ''} from data table"
            )
            self.main_window.sidebar.intel_message_label.setStyleSheet(
                "QLabel {"
                "  font-size: 12px;"
                "  color: #FF9500;"
                "  background: transparent;"
                "  font-weight: 600;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "}"
            )

    def _edit_cycle_timing(self, row_index):
        """Open dialog to manually edit cycle start/end times.

        Args:
            row_index: Row index in cycle table
        """
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QDoubleSpinBox, QPushButton, QFormLayout
        from affilabs.utils.logger import logger

        # Get current cycle data
        if not hasattr(self.main_window, '_loaded_cycles_data') or row_index >= len(self.main_window._loaded_cycles_data):
            logger.warning(f"Cannot edit cycle timing - row {row_index} not found in loaded data")
            return

        cycle_data = self.main_window._loaded_cycles_data[row_index]

        # Get current values
        current_start = cycle_data.get('start_time_sensorgram', 0)
        current_end = cycle_data.get('end_time_sensorgram', 0)
        current_duration = cycle_data.get('duration_minutes', 0)

        # Handle NaN values
        if pd.isna(current_start):
            current_start = 0
        if pd.isna(current_end):
            current_end = current_start + (current_duration * 60 if not pd.isna(current_duration) else 0)
        if pd.isna(current_duration):
            current_duration = (current_end - current_start) / 60 if current_end > current_start else 0

        # Create dialog
        dialog = QDialog(self.main_window)
        dialog.setWindowTitle(f"Edit Timing - Cycle {row_index + 1}")
        dialog.setMinimumWidth(400)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(16)

        # Info label
        cycle_type = cycle_data.get('type', 'Unknown')
        info_label = QLabel(f"<b>{cycle_type} (Cycle {row_index + 1})</b>")
        info_label.setStyleSheet("font-size: 14px; color: #1D1D1F; padding: 8px;")
        layout.addWidget(info_label)

        # Form layout for timing inputs
        form_layout = QFormLayout()
        form_layout.setSpacing(12)

        # Start time input (seconds)
        start_spin = QDoubleSpinBox()
        start_spin.setRange(0, 999999)
        start_spin.setValue(current_start)
        start_spin.setSuffix(" s")
        start_spin.setDecimals(2)
        start_spin.setMinimumWidth(150)
        start_spin.setStyleSheet("""
            QDoubleSpinBox {
                padding: 6px;
                font-size: 13px;
                border: 1px solid #D1D1D6;
                border-radius: 6px;
            }
            QDoubleSpinBox:focus {
                border: 2px solid #007AFF;
            }
        """)
        form_layout.addRow("Start Time:", start_spin)

        # End time input (seconds)
        end_spin = QDoubleSpinBox()
        end_spin.setRange(0, 999999)
        end_spin.setValue(current_end)
        end_spin.setSuffix(" s")
        end_spin.setDecimals(2)
        end_spin.setMinimumWidth(150)
        end_spin.setStyleSheet(start_spin.styleSheet())
        form_layout.addRow("End Time:", end_spin)

        # Duration (calculated, read-only display)
        duration_label = QLabel(f"{current_duration:.2f} min")
        duration_label.setStyleSheet("font-size: 13px; color: #86868B; padding: 6px;")
        form_layout.addRow("Duration:", duration_label)

        # Auto-update duration when times change
        def update_duration():
            start = start_spin.value()
            end = end_spin.value()
            duration_min = (end - start) / 60
            duration_label.setText(f"{duration_min:.2f} min")
            # Validate times
            if end <= start:
                duration_label.setStyleSheet("font-size: 13px; color: #FF3B30; padding: 6px; font-weight: 600;")
            else:
                duration_label.setStyleSheet("font-size: 13px; color: #86868B; padding: 6px;")

        start_spin.valueChanged.connect(update_duration)
        end_spin.valueChanged.connect(update_duration)

        layout.addLayout(form_layout)

        # Button row
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(36)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: #F2F2F7;
                color: #1D1D1F;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
                padding: 0 20px;
            }
            QPushButton:hover {
                background: #E5E5EA;
            }
        """)
        cancel_btn.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_btn)

        save_btn = QPushButton("✓ Save")
        save_btn.setFixedHeight(36)
        save_btn.setStyleSheet("""
            QPushButton {
                background: #007AFF;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
                padding: 0 20px;
            }
            QPushButton:hover {
                background: #0051D5;
            }
        """)

        def save_changes():
            new_start = start_spin.value()
            new_end = end_spin.value()

            # Validate
            if new_end <= new_start:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(
                    dialog,
                    "Invalid Timing",
                    "End time must be after start time!"
                )
                return

            # Update cycle data
            cycle_data['start_time_sensorgram'] = new_start
            cycle_data['end_time_sensorgram'] = new_end
            cycle_data['duration_minutes'] = (new_end - new_start) / 60

            # Update table display
            time_str = f"{cycle_data['duration_minutes']:.1f}m @ {new_start:.0f}s"
            self.cycle_data_table.item(row_index, 2).setText(time_str)

            logger.info(f"✏️ Updated cycle {row_index + 1} timing: {new_start:.2f}s → {new_end:.2f}s ({cycle_data['duration_minutes']:.2f} min)")

            # Show confirmation
            if hasattr(self.main_window, 'sidebar') and hasattr(self.main_window.sidebar, 'intel_message_label'):
                self.main_window.sidebar.intel_message_label.setText(
                    f"✏️ Updated Cycle {row_index + 1} timing"
                )
                self.main_window.sidebar.intel_message_label.setStyleSheet(
                    "QLabel { font-size: 12px; color: #34C759; background: transparent; font-weight: 600; }"
                )

            dialog.accept()

        save_btn.clicked.connect(save_changes)
        button_layout.addWidget(save_btn)

        layout.addLayout(button_layout)

        # Show dialog
        dialog.exec()

    def _update_details_panel(self):
        """Show cycle-specific notes below the table when a cycle is selected."""
        if not hasattr(self, 'details_tab_widget'):
            return

        selected_rows = self.cycle_data_table.selectionModel().selectedRows()
        if not selected_rows:
            self.details_tab_widget.hide()
            return

        row_idx = selected_rows[0].row()

        if not hasattr(self, '_cycle_details_data'):
            self._cycle_details_data = {}

        details = self._cycle_details_data.get(row_idx, {})
        note = details.get('note', '')

        if note and note.strip():
            self.details_notes_text.setText(note.strip())
            self.details_tab_widget.show()
        else:
            self.details_tab_widget.hide()

    def _apply_compact_view_initial(self):
        """Apply initial column visibility based on compact_view flag."""
        if self.compact_view:
            self.cycle_data_table.setColumnHidden(self.TABLE_COL_TIME, True)
            self.cycle_data_table.setColumnHidden(self.TABLE_COL_CONC, True)

    def _toggle_compact_view(self):
        """Toggle between compact and expanded table view."""
        self.compact_view = not self.compact_view

        if self.compact_view:
            # Hide less-important columns in compact view
            self.cycle_data_table.setColumnHidden(self.TABLE_COL_TIME, True)
            self.cycle_data_table.setColumnHidden(self.TABLE_COL_CONC, True)
        else:
            # Show all columns in expanded view
            for col in range(5):
                self.cycle_data_table.setColumnHidden(col, False)

    def _apply_cycle_filter(self, filter_text):
        """Filter cycles by type based on dropdown selection."""
        self.cycle_filter = filter_text

        # Show/hide rows based on filter
        for row in range(self.cycle_data_table.rowCount()):
            cycle_type_item = self.cycle_data_table.item(row, 1)
            if cycle_type_item:
                # Get full cycle type from tooltip (e.g., "Baseline", "Association")
                cycle_type = cycle_type_item.toolTip() or cycle_type_item.text()

                # Check if cycle type matches filter
                if filter_text == "All":
                    show_row = True
                else:
                    # Show row if its type matches the selected filter
                    show_row = filter_text in cycle_type

                self.cycle_data_table.setRowHidden(row, not show_row)

        # Re-apply search filter if active
        if hasattr(self, 'search_box') and self.search_box.text():
            self._apply_search_filter(self.search_box.text())

        # Apply color coding for missing data
        self._apply_row_color_coding()

        # Update metadata stats
        self._update_metadata_stats()

    def _apply_search_filter(self, search_text):
        """Filter table rows based on search text across all columns."""
        search_text = search_text.lower().strip()

        # First, restore all rows that were hidden by previous search
        # (but respect cycle filter)
        for row in range(self.cycle_data_table.rowCount()):
            # Check if row should be visible based on cycle filter
            cycle_type_item = self.cycle_data_table.item(row, 1)
            if cycle_type_item:
                cycle_type = cycle_type_item.toolTip() or cycle_type_item.text()
                # Check if cycle type matches current filter
                if self.cycle_filter == "All":
                    show_by_filter = True
                else:
                    show_by_filter = self.cycle_filter in cycle_type
            else:
                show_by_filter = True

            if not search_text:
                # No search text - show row if cycle filter allows it
                self.cycle_data_table.setRowHidden(row, not show_by_filter)
            elif show_by_filter:
                # Search active - check if row matches
                row_matches = False
                for col in range(self.cycle_data_table.columnCount()):
                    if self.cycle_data_table.isColumnHidden(col):
                        continue

                    item = self.cycle_data_table.item(row, col)
                    if item and search_text in item.text().lower():
                        row_matches = True
                        break

                # Show row only if it matches search AND passes cycle filter
                self.cycle_data_table.setRowHidden(row, not row_matches)
            else:
                # Hidden by cycle filter
                self.cycle_data_table.setRowHidden(row, True)

        # Apply color coding after filtering
        self._apply_row_color_coding()

        # Update metadata stats
        self._update_metadata_stats()

    def _apply_row_color_coding(self):
        """Color code rows based on missing critical information."""
        for row in range(self.cycle_data_table.rowCount()):
            if self.cycle_data_table.isRowHidden(row):
                continue

            # Check for missing concentration (col 3)
            conc_item = self.cycle_data_table.item(row, self.TABLE_COL_CONC)
            conc_missing = not conc_item or not conc_item.text().strip()

            # Apply red background if concentration is missing
            if conc_missing:
                for col in range(self.cycle_data_table.columnCount()):
                    item = self.cycle_data_table.item(row, col)
                    if item:
                        item.setBackground(QColor(255, 230, 230))  # Light red
            else:
                # Clear background (alternating rows handled by stylesheet)
                for col in range(self.cycle_data_table.columnCount()):
                    item = self.cycle_data_table.item(row, col)
                    if item:
                        item.setBackground(QColor(255, 255, 255))  # White

    def _show_columns_menu(self):
        """Show menu to hide/unhide columns (triggered by button click)."""
        from PySide6.QtWidgets import QMenu
        from PySide6.QtCore import QPoint

        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background: white;
                border: 1px solid #D1D1D6;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                font-size: 11px;
            }
            QMenu::item:selected {
                background: #007AFF;
                color: white;
            }
        """)

        # Toggle-able columns: Type(1), Time(2), Conc.(3), ΔSPR(4). Export(0) is not hideable.
        column_names = [
            ("Type",  self.TABLE_COL_TYPE),
            ("Time",  self.TABLE_COL_TIME),
            ("Conc.", self.TABLE_COL_CONC),
            ("ΔSPR",  self.TABLE_COL_DELTA_SPR),
        ]

        # Create checkable actions for each column
        for name, col in column_names:
            action = menu.addAction(name)
            action.setCheckable(True)
            action.setChecked(not self.cycle_data_table.isColumnHidden(col))
            action.setData(col)  # Store column index
            action.triggered.connect(lambda checked, c=col: self._toggle_column_visibility(c, checked))

        # Show menu below the columns button (use stored reference)
        if hasattr(self, 'columns_btn') and self.columns_btn is not None:
            pos = self.columns_btn.mapToGlobal(QPoint(0, self.columns_btn.height()))
            menu.exec(pos)
        else:
            # Fallback: show at cursor
            menu.exec(QCursor.pos())

    def _show_column_visibility_menu(self, position):
        """Show context menu to hide/unhide columns (right-click on header - kept for advanced users)."""
        # Just call the same menu function
        self._show_columns_menu()

    def _toggle_column_visibility(self, col, visible):
        """Toggle column visibility."""
        self.cycle_data_table.setColumnHidden(col, not visible)

    def _load_data_from_excel_with_path_tracking(self):
        """Load Excel file and track the path for later saving."""
        from PySide6.QtWidgets import QFileDialog

        # Open file dialog
        file_path, _ = QFileDialog.getOpenFileName(
            self.main_window,
            "Load Excel File",
            "",
            "Excel Files (*.xlsx);All Files (*)"
        )

        if not file_path:
            return

        # Store the file path for saving later
        self._loaded_file_path = file_path

        # Call the main window's load function
        self.main_window._load_data_from_excel_internal(file_path)

    def _load_data_from_path(self, path: "Path") -> None:
        """Load an Excel file directly from a Path — called by ExperimentBrowserDialog."""
        from pathlib import Path as _Path
        file_path = str(path) if isinstance(path, _Path) else path
        self._loaded_file_path = file_path
        self.main_window._load_data_from_excel_internal(file_path)

    def _open_experiment_browser(self) -> None:
        """Switch to Notes tab (FRS §11.4). Falls back to dialog if Notes tab unavailable."""
        mw = self.main_window
        if hasattr(mw, 'notes_tab') and hasattr(mw, 'navigation_presenter'):
            mw.navigation_presenter.switch_page(2)
            return
        # Fallback: open dialog
        from affilabs.dialogs.experiment_browser_dialog import ExperimentBrowserDialog
        user_manager = getattr(self, "user_manager", None)
        if user_manager is None:
            user_manager = getattr(mw, "user_manager", None)
        dlg = ExperimentBrowserDialog(parent=mw, user_manager=user_manager)
        dlg.file_selected.connect(self._load_data_from_path)
        dlg.exec()

    def _save_cycles_to_excel(self):
        """Save the modified cycle data back to the loaded Excel file."""
        from PySide6.QtWidgets import QMessageBox
        from affilabs.utils.logger import logger
        import pandas as pd

        if not self._loaded_file_path:
            QMessageBox.warning(
                self.main_window,
                "No File Loaded",
                "Please load an Excel file first using the Load button."
            )
            return

        try:
            file_path = Path(self._loaded_file_path)

            if not file_path.exists():
                QMessageBox.critical(
                    self.main_window,
                    "File Not Found",
                    f"The file no longer exists:\n{file_path}"
                )
                self._loaded_file_path = None
                return

            logger.info(f"Saving cycles to Excel: {file_path}")

            # Collect current cycle data from table and _loaded_cycles_data
            updated_cycles = []
            if hasattr(self.main_window, '_loaded_cycles_data'):
                for cycle in self.main_window._loaded_cycles_data:
                    cycle_copy = cycle.copy()
                    updated_cycles.append(cycle_copy)

            if not updated_cycles:
                QMessageBox.warning(
                    self.main_window,
                    "No Cycles",
                    "No cycles to save."
                )
                return

            # Read existing Excel file to preserve other sheets
            excel_sheets = pd.read_excel(file_path, sheet_name=None, engine='openpyxl')

            # Update the Cycles sheet with modified data
            df_cycles = pd.DataFrame(updated_cycles)

            # Write back to Excel, preserving all other sheets
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                # Write Cycles sheet (updated)
                df_cycles.to_excel(writer, sheet_name='Cycles', index=False)
                logger.info(f"✓ Updated Cycles sheet with {len(updated_cycles)} cycles")

                # Write all other sheets unchanged
                for sheet_name, df_sheet in excel_sheets.items():
                    if sheet_name != 'Cycles':  # Skip Cycles as we just wrote it
                        df_sheet.to_excel(writer, sheet_name=sheet_name, index=False)

            logger.info(f"✓ Saved {len(updated_cycles)} cycles back to Excel")

            QMessageBox.information(
                self.main_window,
                "Save Successful",
                f"Saved {len(updated_cycles)} cycles back to Excel file.\n\nFile: {file_path.name}"
            )

        except Exception as e:
            logger.error(f"Failed to save cycles to Excel: {e}", exc_info=True)
            QMessageBox.critical(
                self.main_window,
                "Save Error",
                f"Failed to save cycles to Excel:\n{str(e)}"
            )

    def _export_post_edit_analysis_with_charts(self):
        """Export comprehensive post-edit analysis workbook with interactive Excel charts.

        Creates a complete analysis workbook containing:
        - Raw data (untouched)
        - Processed data (with current UI settings applied)
        - Analysis results (delta SPR measurements, cursor positions)
        - Flag positions (updated marker data)
        - Enhanced cycle metadata
        - Interactive Excel charts (bar charts, timelines, overview)
        """
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from affilabs.utils.logger import logger
        from datetime import datetime
        import pandas as pd

        try:
            # Check if we have data to export
            if not hasattr(self.main_window, '_loaded_cycles_data') or not self.main_window._loaded_cycles_data:
                QMessageBox.warning(
                    self.main_window,
                    "No Data",
                    "No cycles data available for export. Please load data first."
                )
                return

            # Get save location
            default_name = f"SPR_Analysis_with_Charts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            default_dir = self._get_user_export_dir()

            file_path, _ = QFileDialog.getSaveFileName(
                self.main_window,
                "Export Analysis with Charts",
                str(default_dir / default_name),
                "Excel files (*.xlsx)"
            )

            if not file_path:
                return  # User cancelled

            logger.info(f"Starting post-edit analysis export with charts: {file_path}")

            # Get selected cycle indices from checkboxes
            selected_cycle_indices = [idx for idx, is_selected in self._cycle_export_selection.items() if is_selected]
            if not selected_cycle_indices:
                QMessageBox.warning(
                    self.main_window,
                    "No Cycles Selected",
                    "Please check at least one cycle in the Export column to include in the export."
                )
                return

            logger.info(f"Exporting {len(selected_cycle_indices)} selected cycles: {selected_cycle_indices}")

            # 1. Get raw data (untouched)
            raw_data = self._get_raw_data_untouched()

            # 2. Generate processed data with current UI settings
            processed_data = self._get_processed_data_with_edits()

            # 3. Capture current analysis results - FILTERED by selected cycles
            analysis_results = self._get_current_analysis_results()
            if not analysis_results.empty and 'Cycle_ID' in analysis_results.columns:
                # Filter to only selected cycles
                analysis_results = analysis_results[analysis_results.index.isin(selected_cycle_indices)]

            # 4. Get updated flag positions - FILTERED by selected cycles
            flag_data = self._get_updated_flag_positions()
            if not flag_data.empty and 'Cycle_ID' in flag_data.columns:
                # Keep only flags from selected cycles
                selected_cycle_ids = [self.main_window._loaded_cycles_data[i].get('cycle_id', f'Cycle_{i+1}')
                                    for i in selected_cycle_indices if i < len(self.main_window._loaded_cycles_data)]
                flag_data = flag_data[flag_data['Cycle_ID'].isin(selected_cycle_ids)]

            # 5. Get enhanced cycles metadata - FILTERED by selected cycles
            cycles_data = self._get_enriched_cycles_metadata()
            if not cycles_data.empty:
                cycles_data = cycles_data.iloc[selected_cycle_indices]

            # 6. Document export settings
            export_settings = {
                'export_timestamp': datetime.now().isoformat(),
                'user': self.user_manager.get_current_user() if self.user_manager else 'Unknown',
                'smoothing_level': self.edits_smooth_slider.value() if hasattr(self, 'edits_smooth_slider') else 0,
                'baseline_corrected': True,
                'cursor_lock_active': getattr(self, '_delta_spr_cursor_locked', False),
                'locked_distance': getattr(self, '_delta_spr_lock_distance', None),
                'software_version': 'Affilabs Core v2.0',
                'processing_version': '1.0',
                'selected_cycles': len(selected_cycle_indices),
                'total_cycles': len(self.main_window._loaded_cycles_data) if hasattr(self.main_window, '_loaded_cycles_data') else 0
            }

            # 7. Create analysis workbook with charts
            from affilabs.utils.excel_chart_builder import create_analysis_workbook_with_charts

            binding_fit = getattr(self, '_binding_fit_result', None)

            # Augment binding_fit with Rmax calculator values if available
            if binding_fit is not None:
                binding_fit = dict(binding_fit)  # shallow copy — don't mutate cached dict
                binding_fit['rmax_ligand_mw']    = getattr(self, '_ligand_mw', None)
                binding_fit['rmax_analyte_mw']   = getattr(self, '_analyte_mw', None)
                binding_fit['rmax_immob_dspr_ru'] = getattr(self, '_immob_delta_spr_ru', None)
                ligand  = binding_fit['rmax_ligand_mw']
                analyte = binding_fit['rmax_analyte_mw']
                immob   = binding_fit['rmax_immob_dspr_ru']
                if ligand and analyte and immob and ligand > 0:
                    binding_fit['rmax_theoretical_ru'] = (analyte / ligand) * immob
                empirical = binding_fit.get('Rmax_RU')
                theo = binding_fit.get('rmax_theoretical_ru')
                if empirical is not None and theo and theo > 0:
                    binding_fit['rmax_surface_activity_pct'] = (empirical / theo) * 100.0

            create_analysis_workbook_with_charts(
                raw_data=raw_data,
                processed_data=processed_data,
                analysis_results=analysis_results,
                flag_data=flag_data,
                cycles_data=cycles_data,
                export_settings=export_settings,
                output_path=Path(file_path),
                selected_cycles=selected_cycle_indices,
                binding_fit=binding_fit,
            )

            logger.info(f"✓ Created analysis workbook with charts: {Path(file_path).name}")

            QMessageBox.information(
                self.main_window,
                "Export Successful",
                f"Analysis workbook with interactive charts saved successfully!\n\n"
                f"File: {Path(file_path).name}\n"
                f"Sheets: Raw Data, Processed Data, Analysis Results, Flag Positions, "
                f"Cycles Metadata, Export Settings\n"
                f"Charts: Delta SPR bars, Timeline graphs, Flag positions, Overview"
            )

        except Exception as e:
            logger.error(f"Failed to export analysis with charts: {e}", exc_info=True)
            QMessageBox.critical(
                self.main_window,
                "Export Error",
                f"Failed to create analysis workbook with charts:\n{str(e)}\n\n"
                "Note: This feature requires openpyxl For full chart support."
            )

