"""Segment management mixin for DataWindow.

Methods (15 total):
    - quick_segment_update
    - update_segment
    - update_shift_display_box
    - new_segment
    - _insert_segment_into_table
    - save_segment
    - restore_deleted
    - reassert_row
    - delete_row
    - reload_segments
    - send_segments_to_analysis
    - _apply_cycle_fixed_window
    - _set_fixed_x_range
    - _apply_y_padding
    - cycle_marker_style_changed
"""

from __future__ import annotations

from copy import deepcopy

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self

from PySide6.QtWidgets import QTableWidgetItem

from affilabs.ui.ui_processing import Ui_Processing
from affilabs.utils.logger import logger
from affilabs.widgets._dw_models import CYCLE_WINDOW_PADDING_FACTOR, Segment
from affilabs.widgets.message import show_message
from settings import CYCLE_TIME


class SegmentMixin:
    """Segment management methods for DataWindow."""

    def quick_segment_update(self: Self) -> None:
        """Update segments with defaults."""
        if self.current_segment:
            self.update_segment(
                self.current_segment.start,
                self.current_segment.end,
                update=False,
                force=True,
            )

    def update_segment(
        self: Self,
        start: float,
        end: float,
        update: bool,  # noqa: FBT001
        *,
        force: bool = False,
    ) -> None:
        """Update the segments table."""
        if self.ready:
            if self.data_source == "dynamic":
                self.busy = True

            allow_update = True
            if (
                self.viewing
                or self.saving
                or (
                    (self.segment_edit is not None)
                    and (self.data_source == "dynamic")
                    and update
                )
            ):
                allow_update = False

            if (allow_update or force) and self.current_segment is not None:
                self.current_segment.set_time(start, end)
                self.current_segment.add_data(
                    self.data,
                    self.unit,
                    self.current_segment.ref_ch,
                )
                if self.current_segment.error is None:
                    self.SOI_view.update_display(self.current_segment)

                    # Update cycle time shaded region position as time advances
                    if self.full_segment_view.cycle_time_region is not None:
                        cycle_time = self.cycle_manager.get_current_time_minutes()
                        if cycle_time is not None:
                            self.full_segment_view.update_cycle_time_region(cycle_time)
                else:
                    logger.debug(f"{self.current_segment.error}")

            self.update_displayed_values()
            self.busy = False

    def update_shift_display_box(self: Self, shift_data: dict) -> None:
        """Update the shift display box with shift values."""
        # shift_display_box removed from UI - status now in Flow tab sidebar

    def new_segment(self: Self) -> None:
        """Create a new segment."""
        from affilabs.utils.logger import logger as _seg_logger
        _seg_logger.debug("[SOI-ZOOM] new_segment() called — resetting fixed_window + enableAutoRange(x) + reset_user_zoom")
        # Clear gray zone and re-enable auto-ranging
        self.full_segment_view.hide_cycle_time_region()
        self.full_segment_view.fixed_window_active = False
        self.SOI_view.fixed_window_active = False
        self.full_segment_view.plot.enableAutoRange(axis="x", enable=True)
        self.SOI_view.plot.enableAutoRange(axis="x", enable=True)
        # Reset user zoom flag so next cycle gets fresh auto-padding
        self.SOI_view.reset_user_zoom()

        if self.segment_edit is not None:
            self.reassert_row(self.segment_edit)
        self.segment_edit = None
        self.viewing = False
        if isinstance(self.ui, Ui_Processing):
            self.ui.reference_channel_btn.setEnabled(True)
            self.ui.curr_seg_box.setEnabled(True)
        self.full_segment_view.movable_cursors(state=True)
        self.cursors_text_edit(state=True)
        self._get_table_widget().clearSelection()
        self.set_row_properties()
        if self.data_source == "dynamic":
            self.ui.save_segment_btn.setText("Start\nCycle")
            self.ui.save_segment_btn.setStyleSheet(self.original_style)
            self.ui.new_segment_btn.setText("Start at\nLive Time")
            self.ui.new_segment_btn.setStyleSheet(self.original_style)
            if self.live_segment_start is not None:
                self.current_segment = Segment(
                    self.seg_count,
                    self.live_segment_start[0],
                    self.live_segment_start[1],
                )
                self.full_segment_view.move_both_cursors(
                    self.current_segment.start,
                    self.current_segment.end,
                )
                logger.debug(f"returning to live segment {self.current_segment.seg_id}")
                self.live_segment_start = None
            else:
                current_time = self.full_segment_view.get_time()
                self.current_segment = Segment(
                    self.seg_count,
                    current_time,
                    current_time + 2,
                )
                self.full_segment_view.move_both_cursors(
                    self.current_segment.start,
                    self.current_segment.end,
                )
                logger.debug(f"new segment {self.current_segment.seg_id}")
            self.set_live(on=self.live_mode)
        else:
            self.current_segment = Segment(self.seg_count, 0, 1)
            self.update_segment(
                self.full_segment_view.get_left(),
                self.full_segment_view.get_right(),
                update=False,
            )
            self.ui.save_segment_btn.setText("Start\nCycle")
            self.ui.save_segment_btn.setStyleSheet(self.original_style)
            self.ui.new_segment_btn.setText("Start from\nLast Cycle")
            self.ui.new_segment_btn.setStyleSheet(self.original_style)
        self.full_segment_view.block_updates = False
        if self.return_ref is None:
            self.return_ref = self.reference_channel_dlg.ref_ch
        self.set_reference(self.return_ref)
        self.current_segment.ref_ch = self.return_ref
        self.quick_segment_update()
        self.return_ref = None

    def _insert_segment_into_table(self: Self, seg: Segment, row: int) -> None:
        """Insert a segment into the data table at the specified row."""
        table = self._get_table_widget()
        table.blockSignals(True)
        try:
            table.insertRow(row)

            # Sanitize data
            name = str(seg.name)[:50] if seg.name else ""
            note = str(seg.note)[:500] if seg.note else ""
            cycle_type = str(seg.cycle_type) if seg.cycle_type else "Auto-read"

            # Create table items
            table.setItem(row, 0, QTableWidgetItem(name))
            table.setItem(row, 1, QTableWidgetItem(f"{seg.start:.2f}"))
            table.setItem(row, 2, QTableWidgetItem(f"{seg.end:.2f}"))
            table.setItem(row, 3, QTableWidgetItem(f"{seg.shift['a']:.3f}"))
            table.setItem(row, 4, QTableWidgetItem(f"{seg.shift['b']:.3f}"))
            table.setItem(row, 5, QTableWidgetItem(f"{seg.shift['c']:.3f}"))
            table.setItem(row, 6, QTableWidgetItem(f"{seg.shift['d']:.3f}"))
            table.setItem(row, 7, QTableWidgetItem(f"{seg.ref_ch}"))
            table.setItem(row, 8, QTableWidgetItem(cycle_type))
            table.setItem(row, 9, QTableWidgetItem(note))
        except Exception as e:
            logger.error(f"Error creating table items: {e}")
            # Create minimal safe row if there's an error
            for col in range(10):
                if table.item(row, col) is None:
                    table.setItem(row, col, QTableWidgetItem(""))
        finally:
            table.blockSignals(False)

    def save_segment(self: Self) -> None:
        """Save a segment and start a new cycle."""
        if (
            self.data_source == "dynamic"
            and not self.data["rec"]
            and not self.reloading
        ):
            show_message(msg="Data recording not started!", msg_type="Warning")
            return

        self.saving = True

        if self.current_segment:
            try:
                if self.segment_edit:
                    logger.debug(
                        f"saving_edited_segment {self.segment_edit} "
                        f"from {self.current_segment.start} "
                        f"- {self.current_segment.end}",
                    )
                    row = self.segment_edit
                    seg = self.current_segment

                    # Update segment info from table
                    seg.add_info(self.get_info(row))
                    self.delete_row()

                elif self.restoring and self.deleted_segment:
                    logger.debug("Branch: restoring deleted segment")
                    seg = self.deleted_segment
                    row = self.deleted_segment.seg_id

                else:
                    # Check if a cycle is already running (fixed window is active)
                    cycle_already_running = (
                        self.data_source == "dynamic"
                        and hasattr(self, "full_segment_view")
                        and self.full_segment_view.fixed_window_active
                    )

                    if cycle_already_running:
                        logger.info(
                            "[WARN] Cycle already running - completing and saving current cycle first",
                        )

                        # Save the currently running cycle with its current end time
                        current_time = self.full_segment_view.get_time()
                        self.current_segment.end = current_time
                        self.update_segment(
                            self.current_segment.start,
                            self.current_segment.end,
                            update=True,
                            force=True,
                        )

                        # Save the old segment
                        old_segment = self.current_segment
                        old_row = len(self.saved_segments)

                        # Insert old segment into table
                        self._insert_segment_into_table(old_segment, old_row)
                        self.saved_segments.insert(old_row, old_segment)
                        logger.info(
                            f"✓ Previous cycle saved: {old_segment.cycle_type} at row {old_row}",
                        )

                        # Create new segment at current time for the new cycle
                        self.seg_count += 1
                        self.current_segment = Segment(
                            self.seg_count,
                            current_time,
                            current_time + 2,
                        )
                        self.full_segment_view.move_both_cursors(
                            self.current_segment.start,
                            self.current_segment.end,
                        )
                        logger.info(
                            f"✓ New segment created for new cycle: ID {self.seg_count}",
                        )

                    # Set cycle type and time from cycle manager for the current/new segment
                    self.current_segment.cycle_type = (
                        self.cycle_manager.get_current_type()
                    )
                    self.current_segment.cycle_time = (
                        self.cycle_manager.get_current_time_minutes()
                    )

                    seg = self.current_segment
                    row = len(self.saved_segments)

                    if not cycle_already_running:
                        self.seg_count += 1

                    # Apply fixed window and gray zone when cycle starts
                    if self.data_source == "dynamic":
                        cycle_time_minutes = (
                            self.cycle_manager.get_current_time_minutes()
                        )
                        self._apply_cycle_fixed_window(cycle_time_minutes)
                        self.cycle_manager.reset_to_default()

                if (seg is not None) and (row is not None):
                    # Insert segment into table
                    self._insert_segment_into_table(seg, row)

                self.saved_segments.insert(row, self.current_segment)
                self.saving = False
                self._get_table_widget().clearSelection()

            except Exception as e:
                logger.exception(f"error while saving row {e}")
                # Ensure signals are re-enabled even if error occurs
                self._get_table_widget().blockSignals(False)
        else:
            logger.error("error while saveing row no current_segment")

        # Final safety check to ensure signals are always enabled
        self._get_table_widget().blockSignals(False)

    def restore_deleted(self: Self) -> None:
        """Restore a deleted segment."""
        if self.deleted_segment is not None:
            self.restoring = True
            self.save_segment()
            self.deleted_segment = None
            self.restoring = False

    def reassert_row(self: Self, row: int) -> None:
        """Reassert a row in the data cycle table with error handling."""
        try:
            seg = self.saved_segments[row]
            # Block signals to prevent cascading updates
            table = self._get_table_widget()
            table.blockSignals(True)

            # Safely create table items with sanitized data
            name = str(seg.name)[:50] if seg.name else ""
            note = str(seg.note)[:500] if seg.note else ""
            cycle_type = str(seg.cycle_type) if seg.cycle_type else "Auto-read"

            table.setItem(row, 0, QTableWidgetItem(name))
            table.setItem(row, 1, QTableWidgetItem(f"{seg.start:.2f}"))
            table.setItem(row, 2, QTableWidgetItem(f"{seg.end:.2f}"))
            table.setItem(row, 3, QTableWidgetItem(f"{seg.shift['a']:.3f}"))
            table.setItem(row, 4, QTableWidgetItem(f"{seg.shift['b']:.3f}"))
            table.setItem(row, 5, QTableWidgetItem(f"{seg.shift['c']:.3f}"))
            table.setItem(row, 6, QTableWidgetItem(f"{seg.shift['d']:.3f}"))
            table.setItem(row, 7, QTableWidgetItem(f"{seg.ref_ch}"))
            table.setItem(row, 8, QTableWidgetItem(cycle_type))
            table.setItem(row, 9, QTableWidgetItem(note))

            table.blockSignals(False)
        except Exception as e:
            logger.error(f"Error reasserting table row {row}: {e}")
            self._get_table_widget().blockSignals(
                False,
            )  # Ensure signals are re-enabled

    def delete_row(self: Self, *, first_available: bool = False) -> None:
        """Delete a row in the data cycle table."""
        if len(self.saved_segments) == 0:
            return

        row = None
        new_seg_trigger = False

        if first_available:
            self.deleted_segment = self._get_table_manager().delete_row(
                saved_segments=self.saved_segments,
                first_available=True,
            )
        else:
            if self.viewing:
                row = self._get_table_widget().currentRow()
                new_seg_trigger = True
            elif self.segment_edit is not None:
                row = self.segment_edit
                new_seg_trigger = True

            self.deleted_segment = self._get_table_manager().delete_row(
                row=row,
                saved_segments=self.saved_segments,
            )

            if new_seg_trigger and not self.saving:
                self.new_segment()

    def reload_segments(self: Self, time_shift: float | None = None) -> None:
        """Reload segments."""
        logger.debug("reloading segments")
        self.reloading = True
        if (
            self.data_source == "dynamic"
            and self.live_segment_start is None
            and self.current_segment
        ):
            self.live_segment_start = [
                deepcopy(self.current_segment.start),
                deepcopy(self.current_segment.end),
            ]
        for row in range(self._get_table_widget().rowCount()):
            self.segment_edit = row
            self.current_segment = self.saved_segments[row]
            if time_shift is not None:
                self.current_segment.shift_time(time_shift)
            self.current_segment.add_data(
                self.data,
                self.unit,
                self.reference_channel_id,
            )
            self.save_segment()
        self.reloading = False
        self.new_segment()

    def send_segments_to_analysis(self: Self) -> None:
        """Send segements to data analysis."""
        self.send_to_analysis_sig.emit(self.data, self.saved_segments, self.unit)

    def _apply_cycle_fixed_window(self: Self, cycle_time_minutes: float | None) -> None:
        """Apply fixed window and cycle markers for cycle start."""
        if cycle_time_minutes is None or cycle_time_minutes <= 0:
            logger.warning("Invalid cycle time, skipping fixed window")
            return

        logger.info(
            f"Cycle started: {self.current_segment.cycle_type}, {cycle_time_minutes} min",
        )

        # Calculate window parameters once
        window_seconds = cycle_time_minutes * 60 * CYCLE_WINDOW_PADDING_FACTOR
        start_time = self.full_segment_view.left_cursor_pos
        end_time = start_time + window_seconds

        # Apply fixed window to both graphs
        self._set_fixed_x_range(
            self.full_segment_view,
            start_time,
            end_time,
            "Sensorgram",
        )
        self._set_fixed_x_range(self.SOI_view, 0, window_seconds, "SOI")

        # Apply Y padding with auto-range enabled
        for plot, name in [
            (self.full_segment_view.plot, "Sensorgram"),
            (self.SOI_view.plot, "SOI"),
        ]:
            self._apply_y_padding(plot, name)

        # Show cycle markers (after ranges are set)
        self.full_segment_view.show_cycle_time_region(cycle_time_minutes)

        # Force immediate visual update
        self.full_segment_view.plot.update()
        self.SOI_view.plot.update()

        logger.debug(f"Fixed window applied: {window_seconds:.0f}s")

    def _set_fixed_x_range(
        self: Self,
        view,
        start: float,
        end: float,
        name: str,
    ) -> None:
        """Set fixed X range on a view and disable X auto-range."""
        view.fixed_window_active = True
        view.plot.getViewBox().setXRange(start, end, padding=0)
        view.plot.enableAutoRange(axis="x", enable=False)
        view.plot.enableAutoRange(axis="y", enable=True)
        logger.debug(f"{name}: X range [{start:.1f}, {end:.1f}]s")

    def _apply_y_padding(self: Self, plot, graph_name: str) -> None:
        """Ensure Y-axis auto-range is enabled for live data updates."""
        plot.enableAutoRange(axis="y", enable=True)
        logger.debug(f"{graph_name}: Y auto-range enabled")

    def cycle_marker_style_changed(self: Self, style: str) -> None:
        """Handle cycle marker style change - re-render if cycle is active."""
        logger.info(f"Cycle marker style changed to: {style}")

        # Only re-render if currently in an active cycle
        if not (
            hasattr(self, "full_segment_view")
            and self.full_segment_view.fixed_window_active
        ):
            return

        cycle_time = (
            self.cycle_manager.get_current_time_minutes()
            if hasattr(self, "cycle_manager")
            else CYCLE_TIME
        )
        if cycle_time and cycle_time > 0:
            self.full_segment_view.hide_cycle_time_region()
            self.full_segment_view.show_cycle_time_region(cycle_time)
            logger.info("✓ Cycle markers re-rendered")
