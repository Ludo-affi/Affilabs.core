"""Cycle, Queue, Recording, and Autosave Mixin for Affilabs.core

This mixin provides cycle/queue management, recording control, and autosave
functionality for the main application. Extracted from main.py for modularity.

Methods (13 total):
===================
Cycle/Queue Management:
    - _connect_queue_widgets
    - _delete_selected_cycles
    - _confirm_clear_queue
    - _on_queue_changed
    - _verify_cycle_table_connections
    - _cancel_active_cycle
    - _update_cycle_data_table

Recording Control:
    - _on_record_baseline_clicked
    - _on_recording_start_requested
    - _on_recording_stop_requested
    - _on_clear_graphs_requested

Autosave:
    - _do_deferred_autosave
    - _autosave_cycle_data

Dependencies:
    - pathlib.Path (file path construction)
    - PySide6.QtCore.Qt (Qt constants)
    - PySide6.QtWidgets.QMessageBox (confirmation dialogs, local imports)
    - affilabs.core.experiment_clock.TimeBase (time conversion)
    - affilabs.utils.logger / loguru (application logger)

Last Updated: 2026-02-18
"""

from pathlib import Path

from PySide6.QtCore import Qt

from affilabs.core.experiment_clock import TimeBase

# Logger is assumed to be available at module level in main.py context
try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class CycleMixin:
    """Mixin providing cycle/queue management, recording, and autosave functionality.

    This mixin is intended to be mixed into the main application class.
    It assumes the following attributes are available:
        - self.main_window: Main window instance with UI elements
        - self.queue_presenter: QueuePresenter instance
        - self.segment_queue: List of queued cycle segments
        - self.recording_mgr: RecordingManager instance
        - self.buffer_mgr: BufferManager instance
        - self.clock: ExperimentClock instance
        - self.data_mgr: DataManager instance
        - self.recording_events: RecordingEventCoordinator instance
        - self.graph_events: GraphEventCoordinator instance
        - self._current_cycle: Currently running cycle (or None)
        - self._sidebar_widget: Method to get sidebar widget by name
        - self._session_epoch: Session epoch counter
        - self.sensogram_presenter: SensogramPresenter instance
        - self.hardware_mgr: HardwareManager instance
    """

    # =========================================================================
    # CYCLE/QUEUE MANAGEMENT
    # =========================================================================

    def _connect_queue_widgets(self):
        """Connect new queue widgets (QueueSummaryWidget and QueueToolbar) to presenter."""
        if not hasattr(self.main_window, 'sidebar'):
            logger.warning("No sidebar found - skipping queue widget connections")
            return

        sidebar = self.main_window.sidebar

        # Connect QueueSummaryWidget to presenter
        if hasattr(sidebar, 'summary_table'):
            sidebar.summary_table.set_presenter(self.queue_presenter)
            logger.debug("✓ QueueSummaryWidget connected to presenter")

            # Connect widget signals for operations
            sidebar.summary_table.cycle_reordered.connect(
                lambda from_idx, to_idx: self.queue_presenter.reorder_cycle(from_idx, to_idx)
            )
            sidebar.summary_table.cycles_deleted.connect(
                lambda indices: self.queue_presenter.delete_cycles(indices) if indices else None
            )
            logger.debug("✓ QueueSummaryWidget drag-drop and delete signals connected")

        # Timeline widget is now in popup dialog (not in sidebar)
        # Connection handled in _open_timeline_dialog when dialog is opened

        # Connect presenter signals for auto-refresh (replaces manual _update_summary_table calls)
        self.queue_presenter.queue_changed.connect(self._on_queue_changed)
        logger.debug("✓ Queue auto-refresh enabled (presenter.queue_changed signal)")

        # Connect Start Queued Run button
        if hasattr(sidebar, 'queued_run_started'):
            sidebar.queued_run_started.connect(self._on_start_queued_run)
            logger.debug("✓ Start Queued Run button connected")

        # Connect Queue Cancel (Stop Run button)
        if hasattr(sidebar, 'queue_cancel_requested'):
            sidebar.queue_cancel_requested.connect(self._cancel_active_cycle)
            logger.debug("✓ Queue Cancel (Stop Run) button connected")

        # Connect Next Cycle button
        if hasattr(sidebar, 'next_cycle_requested'):
            sidebar.next_cycle_requested.connect(self._on_next_cycle)
            logger.debug("✓ Next Cycle button connected")

        # Connect Clear Queue button (sidebar signal path)
        if hasattr(sidebar, 'queue_cleared'):
            sidebar.queue_cleared.connect(self._confirm_clear_queue)
            logger.debug("✓ Clear Queue button connected")

    def _delete_selected_cycles(self):
        """Delete selected cycles from queue (called by toolbar Delete button)."""
        if not (tbl := self._sidebar_widget('summary_table')):
            return

        selected_indices = tbl.get_selected_indices()
        if not selected_indices:
            logger.info("No cycles selected for deletion")
            return

        from PySide6.QtWidgets import QMessageBox
        count = len(selected_indices)
        reply = QMessageBox.question(
            self.main_window,
            "Delete Cycles",
            f"Delete {count} selected {'cycle' if count == 1 else 'cycles'}?\n\nYou can undo this with Ctrl+Z.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            success = self.queue_presenter.delete_cycles(selected_indices)
            if success:
                self.segment_queue = self.queue_presenter.get_queue_snapshot()
                logger.info(f"🗑️ Deleted {count} cycles from queue")

    def _confirm_clear_queue(self):
        """Clear entire queue with confirmation (called by toolbar Clear All button)."""
        if self.queue_presenter.get_queue_size() == 0:
            logger.info("Queue is already empty")
            return

        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self.main_window,
            "Clear Queue",
            f"Clear all {self.queue_presenter.get_queue_size()} cycles from queue?\n\nYou can undo this with Ctrl+Z.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.queue_presenter.clear_queue()
            self.segment_queue = self.queue_presenter.get_queue_snapshot()
            logger.info("🗑️ Queue cleared")

            # Reset method name to default
            if method_label := self._sidebar_widget('method_name_label'):
                method_label.setText("Untitled Method")

    def _on_queue_changed(self):
        """Handle queue changes - update UI elements that don't auto-refresh.

        Summary table auto-refreshes via presenter.queue_changed signal.
        This handler updates:
        - Progress bar
        - Queue status label
        - Button visibility (Start Run, Clear Queue)
        """
        queue_size = self.queue_presenter.get_queue_size()

        # Update progress bar with current queue state
        if bar := self._sidebar_widget('queue_progress_bar'):
            try:
                cycles = self.queue_presenter.get_queue_snapshot()
                completed_cycles = self.queue_presenter.get_completed_cycles()
                bar.set_cycles(cycles, completed_cycles)
                if hasattr(self, '_current_cycle') and self._current_cycle:
                    current_index = 0
                else:
                    current_index = -1
                bar.set_current_index(current_index)
            except Exception as e:
                logger.debug(f"Could not update progress bar: {e}")

        # Update queue status label
        if lbl := self._sidebar_widget('queue_status_label'):
            if queue_size == 0:
                lbl.setText("Queue: 0 cycles | Click 'Add to Queue' to plan batch runs")
            elif queue_size == 1:
                lbl.setText("Queue: 1 cycle ready")
            else:
                lbl.setText(f"Queue: {queue_size} cycles ready")

        # Show/hide Start Run button based on queue size
        if btn := self._sidebar_widget('start_run_btn'):
            btn.setVisible(queue_size > 0)

        # Show/hide Clear Queue button based on queue size
        if btn := self._sidebar_widget('clear_queue_btn'):
            btn.setVisible(queue_size > 0)

        # Update queue size label in table footer
        if lbl := self._sidebar_widget('queue_size_label'):
            if queue_size == 0:
                lbl.setText("No cycles queued")
            elif queue_size == 1:
                lbl.setText("1 cycle queued")
            else:
                lbl.setText(f"{queue_size} cycles queued")

        # Update status bar queue status
        if hasattr(self.main_window, 'update_status_queue'):
            self.main_window.update_status_queue(queue_size)

    def _verify_cycle_table_connections(self):
        """Verify all cycle table connections are properly set up."""
        logger.debug("Verifying cycle table connections...")

        # Quick verification with minimal logging
        errors = []

        # Check 1: Main window has edits_tab
        if not hasattr(self.main_window, 'edits_tab'):
            errors.append("main_window.edits_tab missing")
        elif not hasattr(self.main_window.edits_tab, 'cycle_data_table'):
            errors.append("edits_tab.cycle_data_table missing")

        # Check 2: Sidebar has method_tab_builder
        if hasattr(self.main_window, 'sidebar'):
            if builder := self._sidebar_widget('method_tab_builder'):
                if not (hasattr(builder, '_app_reference') and builder._app_reference is not None):
                    errors.append("method_tab_builder app reference not set")
            else:
                errors.append("sidebar.method_tab_builder missing")
        else:
            errors.append("main_window.sidebar missing")

        # Check 3: Segment queue exists
        if not hasattr(self, 'segment_queue'):
            errors.append("app.segment_queue missing")

        if errors:
            logger.warning(f"Cycle table setup issues: {'; '.join(errors)}")
        else:
            logger.debug("✓ Cycle table connections verified")

    def _cancel_active_cycle(self):
        """Cancel the currently-running cycle without starting the next one.

        Stops both cycle timers, clears cycle state, unlocks the queue,
        and restores the intelligence refresh timer.  Unlike
        ``_on_cycle_completed`` this does **not** auto-start the next
        queued cycle, so the run truly stops.

        Also saves the partial cycle data to the Edits table automatically.
        """
        # Stop both timers (display-update + end-of-cycle)
        if hasattr(self, '_cycle_timer') and self._cycle_timer.isActive():
            self._cycle_timer.stop()
        if hasattr(self, '_cycle_end_timer') and self._cycle_end_timer.isActive():
            self._cycle_end_timer.stop()

        # Hide the progress bar (without affecting injection buttons)
        try:
            from affilabs.widgets.datawindow import DataWindow
            for widget in self.main_window.findChildren(DataWindow):
                if hasattr(widget, 'ui') and hasattr(widget.ui, 'progress_bar'):
                    widget.ui.progress_bar.hide()
                    widget.ui.progress_bar.setValue(0)
                    logger.debug("✓ Progress bar hidden (cycle aborted)")
                    break
        except Exception as e:
            logger.warning(f"⚠️ Could not hide progress bar: {e}")

        # Resume the 5 s intelligence refresh timer
        if hasattr(self.main_window, 'intelligence_refresh_timer'):
            self.main_window.intelligence_refresh_timer.start(5000)

        # Clear Active Cycle graph intelligence footer
        try:
            if hasattr(self.main_window, 'cycle_of_interest_graph') and hasattr(self.main_window.cycle_of_interest_graph, 'intelligence_footer'):
                footer = self.main_window.cycle_of_interest_graph.intelligence_footer
                footer.update_cycle_info(None)  # Clear cycle data (shows "No cycle loaded")

                # Reset status indicators to idle
                status_data = {
                    'build': '✅ Built',
                    'detection': '⚪ Idle',
                    'flags': 0,
                    'injection': '⚪ Ready',
                }
                footer.update_status(status_data)

        except Exception as e:
            logger.debug(f"⚠️ Could not clear intelligence footer: {e}")

        # Save incomplete cycle data before clearing
        had_cycle = self._current_cycle is not None
        if had_cycle and self._current_cycle is not None:
            # Get current sensorgram time as early end time (convert display → RAW_ELAPSED)
            end_sensorgram_time = None
            if hasattr(self.main_window, 'full_timeline_graph'):
                timeline = self.main_window.full_timeline_graph
                if hasattr(timeline, 'stop_cursor'):
                    end_sensorgram_time = self.clock.convert(
                        timeline.stop_cursor.value(), TimeBase.DISPLAY, TimeBase.RAW_ELAPSED
                    )

            # Set end time on cycle (even if incomplete)
            if end_sensorgram_time is not None:
                self._current_cycle.end_time_sensorgram = end_sensorgram_time
                logger.info(f"💾 Saving incomplete cycle (stopped at {end_sensorgram_time:.2f}s)")

            # Export and save to table and recording
            try:
                cycle_export_data = self._current_cycle.to_export_dict(clock=self.clock)

                # Save to Edits table
                if hasattr(self.main_window, 'edits_tab'):
                    self.main_window.edits_tab.add_cycle(cycle_export_data)
                    logger.info(f"✓ Incomplete {cycle_export_data.get('type', 'cycle')} saved to Edits table")

                # Save to recording if active
                if hasattr(self, 'recording_mgr') and self.recording_mgr.is_recording:
                    self.recording_mgr.add_cycle(cycle_export_data)
                    logger.info(f"✓ Incomplete cycle added to recording")

                # Mark as completed in queue presenter
                if hasattr(self, 'queue_presenter'):
                    self.queue_presenter.mark_cycle_completed(self._current_cycle)
                    self.queue_presenter.advance_method_progress()

            except Exception as e:
                logger.error(f"Failed to save incomplete cycle: {e}")

        # Clear cycle state
        self._current_cycle = None
        self._cycle_end_time = None

        # Close notes popup and hide button (no active cycle)
        if hasattr(self.main_window, '_close_cycle_notes_popup'):
            self.main_window._close_cycle_notes_popup()
        if hasattr(self.main_window, '_update_cycle_note_button'):
            self.main_window._update_cycle_note_button(False, visible=False)

        # Clear pause state and unlock queue so user can edit it again
        try:
            if self.queue_presenter.is_paused():
                self.queue_presenter.resume_queue()
            self.queue_presenter.unlock_queue()
        except Exception:
            pass

        # Remove next-cycle warning line from graph
        if hasattr(self, '_next_cycle_warning_line') and self._next_cycle_warning_line is not None:
            try:
                if hasattr(self.main_window, 'cycle_of_interest_graph'):
                    self.main_window.cycle_of_interest_graph.removeItem(self._next_cycle_warning_line)
            except Exception:
                pass
            self._next_cycle_warning_line = None

        # Clear running cycle highlight from queue table
        if tbl := self._sidebar_widget('summary_table'):
            tbl.set_running_cycle(None)
            logger.debug("✓ Queue table highlight cleared (Cancel)")

        # Change Stop Run button back to Start Run
        self._set_start_button_to_start_mode()

        if btn := self._sidebar_widget('next_cycle_btn'):
            btn.setEnabled(False)

        if had_cycle:
            logger.debug("🛑 Active cycle cancelled – timers stopped, queue unlocked")

    def _update_cycle_data_table(self):
        """Update the Flags column in cycle data table with flag information."""
        self.graph_events.update_cycle_data_table()

    # =========================================================================
    # RECORDING CONTROL
    # =========================================================================

    def _on_record_baseline_clicked(self):
        """Handle Record Baseline Data button click."""
        logger.info("="*80)
        logger.info("[HANDLER] _on_record_baseline_clicked CALLED")
        logger.info("="*80)
        self.recording_events.on_record_baseline_clicked()

    def _on_recording_start_requested(self):
        """User requested to start recording - show confirmation popup first."""
        from PySide6.QtWidgets import QMessageBox
        from affilabs.utils.time_utils import for_filename

        logger.info("[RECORD-HANDLER] Recording start requested - showing confirmation")

        # Log current queue state for debugging
        logger.info(f"📋 Current queue state: {len(self.segment_queue)} cycles")
        for i, cycle in enumerate(self.segment_queue):
            logger.info(f"  [{i}] {cycle.name} ({cycle.type}, {cycle.length_minutes} min)")

        # Reset cycle type counter for new recording session
        if hasattr(self.main_window, '_cycle_type_counts'):
            self.main_window._cycle_type_counts = {}

        # Prepare filename and destination
        timestamp = for_filename().replace(".", "_")
        default_filename = f"AffiLabs_data_{timestamp}"

        # Always resolve user-specific directory dynamically (same as Edits tab)
        # This ensures Record button always saves to Documents/Affilabs Data/<username>/SPR_data/
        destination = str(self.recording_mgr.get_user_output_directory())
        current_user = self._get_current_user()
        logger.info(f"✅ Recording destination for '{current_user or 'Default'}': {destination}")

        # Keep sidebar export_dest_input in sync with resolved user path
        if w := self._sidebar_widget('export_dest_input'):
            w.setText(destination)

        # Get filename from UI or use default
        filename = self.main_window.sidebar.export_filename_input.text() or default_filename

        # Use Excel format (format selector was removed for consistency)
        extension = ".xlsx"

        # Ensure filename has extension
        if not any(filename.endswith(ext) for ext in ['.xlsx', '.csv', '.json', '.h5']):
            filename = filename + extension

        full_path = Path(destination) / filename

        # Show confirmation dialog
        msg = QMessageBox(self.main_window)
        msg.setIcon(QMessageBox.Question)
        msg.setWindowTitle("Start Recording")

        # Format message with prominent path styling
        message_html = (
            "<p style='font-size: 13px;'>Data will be recorded as:</p>"
            f"<p style='font-size: 14px; font-weight: bold; color: #1D1D1F; background: #F5F5F7; padding: 8px; border-radius: 4px;'>"
            f"{filename}</p>"
            "<p style='font-size: 13px; margin-top: 12px;'>In folder:</p>"
            f"<p style='font-size: 13px; font-weight: 600; color: #007AFF; background: #F0F6FF; padding: 8px; border-radius: 4px; font-family: monospace;'>"
            f"{destination}</p>"
        )

        msg.setText(message_html)
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setInformativeText("Change settings in Export tab if needed, or start live recording now.")

        start_btn = msg.addButton("▶️ Start Recording", QMessageBox.AcceptRole)
        cancel_btn = msg.addButton("Cancel", QMessageBox.RejectRole)
        msg.setDefaultButton(start_btn)

        msg.exec()

        if msg.clickedButton() == cancel_btn:
            logger.info("Recording cancelled by user")
            # Reset button state since recording didn't start
            self.main_window.set_recording_state(is_recording=False)
            return

        # User confirmed - start recording with file
        logger.info(f"Starting recording to file: {full_path}")

        # Get the live data front directly from the buffer (RAW_ELAPSED coords).
        # NOTE: clock.raw_elapsed_now() returns 0 because start_experiment() is never
        # called — the clock is disconnected from the buffer's own timestamp origin.
        # The live front is simply the latest raw timestamp in any channel's timeline.
        raw_now = 0.0
        try:
            for _ch in ['a', 'b', 'c', 'd']:
                _buf = getattr(self.buffer_mgr, 'timeline_data', {}).get(_ch)
                if _buf is not None and hasattr(_buf, 'time') and len(_buf.time) > 0:
                    raw_now = max(raw_now, float(_buf.time[-1]))
        except Exception:
            pass
        recording_start_elapsed = raw_now

        # Tell the clock where recording t=0 is, then pass to recording manager
        self.clock.start_recording_at(recording_start_elapsed)
        self.recording_mgr.start_recording(filename=str(full_path), time_offset=recording_start_elapsed)

        # Add visual marker on Live Sensorgram showing recording started
        if hasattr(self.main_window, 'full_timeline_graph'):
            try:
                import pyqtgraph as pg
                from PySide6.QtGui import QColor

                # Marker sits at the live data front in DISPLAY coords:
                # display = raw - display_offset  (same formula the graph uses)
                marker_position = raw_now - self.clock.display_offset

                logger.info(f"Recording marker: raw_time={recording_start_elapsed:.3f}s, offset={self.clock.display_offset:.3f}s, display_pos={marker_position:.3f}s")

                # Create vertical green dashed line at recording start time
                marker = pg.InfiniteLine(
                    pos=marker_position,
                    angle=90,  # Vertical
                    pen=pg.mkPen(color=QColor(34, 139, 34), width=2, style=Qt.DashLine),
                    movable=False,
                    label='REC',
                    labelOpts={
                        'position': 0.95,
                        'color': (34, 139, 34),
                        'fill': (255, 255, 255, 200),
                        'movable': False
                    }
                )

                # Store marker reference for cleanup
                if not hasattr(self, '_recording_markers'):
                    self._recording_markers = []
                self._recording_markers.append(marker)

                # Add to plot
                self.main_window.full_timeline_graph.addItem(marker)
                logger.info(f"✓ Recording marker added at display position t={marker_position:.1f}s")
            except Exception as e:
                logger.warning(f"Could not add recording marker: {e}")

        # Update UI state
        self.main_window.set_recording_state(is_recording=True, filename=filename)

    def _on_recording_stop_requested(self):
        """User requested to stop recording."""
        logger.info("Recording stop requested...")

        # Stop the recording
        self.recording_mgr.stop_recording()

        # Cancel any running cycle so the queue doesn't keep executing
        self._cancel_active_cycle()

        # Update UI state to reflect recording stopped
        self.main_window.set_recording_state(is_recording=False)

    def _on_clear_graphs_requested(self):
        """Handle clear graphs button click - clear all buffer data and reset timeline."""
        try:
            # Increment session epoch - invalidates all old data in one atomic operation
            self._session_epoch += 1

            # Reset experiment start time and display offset
            self.clock.reset()

            # Clear processing queue to remove old data with old timestamps
            if hasattr(self, "_spectrum_queue") and self._spectrum_queue:
                # Drain the queue
                cleared_count = 0
                try:
                    while not self._spectrum_queue.empty():
                        self._spectrum_queue.get_nowait()
                        cleared_count += 1
                except:
                    pass
                if cleared_count > 0:
                    logger.info(f"[OK] Cleared {cleared_count} items from processing queue")

            # Clear all data buffers
            if hasattr(self, "buffer_mgr") and self.buffer_mgr:
                self.buffer_mgr.clear_all()
            else:
                logger.warning("[WARN] Buffer manager not available")

            # Clear visual graph data
            if hasattr(self, "sensogram_presenter") and self.sensogram_presenter:
                self.sensogram_presenter.clear_all_graphs()
                logger.debug("Graph visual data cleared")

            # Clear recording markers from Live Sensorgram
            if hasattr(self, '_recording_markers') and hasattr(self.main_window, 'full_timeline_graph'):
                marker_count = len(self._recording_markers)
                for marker in self._recording_markers:
                    try:
                        self.main_window.full_timeline_graph.removeItem(marker)
                    except Exception as e:
                        logger.debug(f"Could not remove recording marker: {e}")
                self._recording_markers.clear()
                logger.info(f"[OK] Cleared {marker_count} recording markers")

            # Reset cursors to position 0 AFTER clearing graphs
            if hasattr(self.main_window, 'full_timeline_graph'):
                timeline = self.main_window.full_timeline_graph
                if hasattr(timeline, 'start_cursor') and timeline.start_cursor:
                    timeline.start_cursor.setValue(0)
                    timeline.start_cursor.setPos(0)  # Force position update
                if hasattr(timeline, 'stop_cursor') and timeline.stop_cursor:
                    timeline.stop_cursor.setValue(0)
                    timeline.stop_cursor.setPos(0)  # Force position update

            logger.debug("Graphs cleared and cursors reset to t=0")

        except Exception as e:
            logger.error(f"[ERROR] Error clearing buffer data: {e}", exc_info=True)

    # =========================================================================
    # AUTOSAVE
    # =========================================================================

    def _do_deferred_autosave(self):
        """Execute pending autosave operation after delay to avoid USB conflicts."""
        if hasattr(self, "_pending_autosave") and self._pending_autosave is not None:
            start_time, stop_time = self._pending_autosave
            self._pending_autosave = None
            self._autosave_cycle_data(start_time, stop_time)

    def _autosave_cycle_data(self, start_time: float, stop_time: float):
        """Automatically save cycle data to session folder."""
        from affilabs.utils.export_helpers import ExportHelpers

        ExportHelpers.autosave_cycle_data(self, start_time, stop_time)

    # ------------------------------------------------------------------ #
    # Cycle display / completion                                           #
    # ------------------------------------------------------------------ #

    def _update_cycle_display(self):
        """Update Active Cycle overlay with cycle progress (called by _cycle_timer)."""
        import time

        if not self._current_cycle or not self._cycle_end_time:
            return

        now = time.time()
        total_sec = self._current_cycle.get_duration_seconds()
        elapsed_sec = total_sec - max(0, self._cycle_end_time - now)
        remaining_sec = max(0, self._cycle_end_time - now)

        cycle_type = self._current_cycle.type
        cycle_num = self._current_cycle.cycle_num
        total_cycles = self._current_cycle.total_cycles

        elapsed_min = int(elapsed_sec // 60)
        elapsed_sec_rem = int(elapsed_sec % 60)
        total_min = int(total_sec // 60)
        total_sec_rem = int(total_sec % 60)

        next_cycle_warning = ""
        if remaining_sec <= 10 and remaining_sec > 0 and self.segment_queue:
            next_cycle = self.segment_queue[0]
            next_type = next_cycle.type
            if next_type == "Concentration":
                next_type = "Binding"
            elif next_type == "Binding":
                next_type = "Bind."
            elif next_type == "Kinetic":
                next_type = "Kin."

            if hasattr(next_cycle, '_concentrations') and next_cycle._concentrations:
                if 'ALL' in next_cycle._concentrations:
                    conc_value = next_cycle._concentrations['ALL']
                    units = getattr(next_cycle, '_units', 'nM')
                    next_type = f"{next_type} {conc_value}{units}"

            next_cycle_warning = f" → Next: {next_type} in {int(remaining_sec)}s"

        if hasattr(self.main_window.sidebar, "intel_message_label"):
            msg = (
                f"⏱ {cycle_type} (Cycle {cycle_num}/{total_cycles}) - "
                f"{elapsed_min:02d}:{elapsed_sec_rem:02d}/{total_min:02d}:{total_sec_rem:02d}"
                f"{next_cycle_warning}"
            )
            self.main_window.sidebar.intel_message_label.setText(msg)
            if next_cycle_warning:
                self.main_window.sidebar.intel_message_label.setStyleSheet(
                    "font-size: 12px; color: #FF9500; background: transparent;"
                    "font-weight: 600; font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
            else:
                self.main_window.sidebar.intel_message_label.setStyleSheet(
                    "font-size: 12px; color: #007AFF; background: transparent;"
                    "font-weight: 600; font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )

        self._update_next_cycle_warning_visual(remaining_sec, total_sec)

        try:
            if hasattr(self.main_window, 'cycle_of_interest_graph'):
                graph = self.main_window.cycle_of_interest_graph
                if hasattr(graph, 'update_delta_overlay'):
                    overlay_type = f"{cycle_type} (Cycle {cycle_num}/{total_cycles})"
                    if next_cycle_warning:
                        overlay_type += next_cycle_warning
                    graph.update_delta_overlay(
                        cycle_type=overlay_type,
                        elapsed_sec=elapsed_sec,
                        total_sec=total_sec,
                    )
        except Exception as e:
            logger.warning(f"Could not update cycle overlay: {e}")

    def _update_next_cycle_warning_visual(self, remaining_sec: float, total_sec: float):
        """Show/hide orange warning line on active cycle graph when <10s to next cycle."""
        try:
            if not hasattr(self.main_window, 'cycle_of_interest_graph'):
                return
            if not isinstance(remaining_sec, (int, float)) or not isinstance(total_sec, (int, float)):
                return
            if remaining_sec < 0 or total_sec <= 0 or remaining_sec > 1e6 or total_sec > 1e6:
                return

            graph = self.main_window.cycle_of_interest_graph
            warning_time = max(0, total_sec - 10.0)
            show_warning = remaining_sec <= 10 and remaining_sec > 0 and self.segment_queue

            if show_warning:
                if self._next_cycle_warning_line is None:
                    import pyqtgraph as pg
                    from PySide6.QtCore import Qt
                    self._next_cycle_warning_line = pg.InfiniteLine(
                        pos=warning_time,
                        angle=90,
                        pen=pg.mkPen(color='#FF1493', width=3, style=Qt.PenStyle.DashLine),
                        movable=False,
                        label=f'Next: {int(remaining_sec)}s',
                        labelOpts={
                            'position': 0.95,
                            'color': (255, 20, 147),
                            'fill': (255, 20, 147, 80),
                            'movable': False,
                        }
                    )
                    graph.addItem(self._next_cycle_warning_line)

                self._next_cycle_warning_line.setPos(warning_time)
                if hasattr(self._next_cycle_warning_line, 'label'):
                    self._next_cycle_warning_line.label.setText(f'Next: {int(remaining_sec)}s')
                self._next_cycle_warning_line.show()
            else:
                if self._next_cycle_warning_line is not None:
                    self._next_cycle_warning_line.hide()
        except Exception as e:
            logger.debug(f"Error updating next cycle warning visual: {e}")

    def _on_cycle_completed(self):
        """Handle cycle completion — auto-start next or switch to auto-read."""
        if not self._current_cycle:
            return

        cycle_type = self._current_cycle.type
        cycle_num = self._current_cycle.cycle_num
        logger.info(f"✓ Cycle {cycle_num} completed: {cycle_type}")

        self._cycle_timer.stop()
        # Ensure the one-shot end timer doesn't fire again (e.g. if Next Cycle was pressed early)
        if hasattr(self, '_cycle_end_timer') and self._cycle_end_timer.isActive():
            self._cycle_end_timer.stop()
        self.flag_mgr.clear_flags_for_new_cycle()

        end_sensorgram_time = None
        if hasattr(self.main_window, 'full_timeline_graph'):
            timeline = self.main_window.full_timeline_graph
            if hasattr(timeline, 'stop_cursor'):
                # stop_cursor is in DISPLAY coords — convert to RAW_ELAPSED
                # to match sensorgram_time (set at cycle start in RAW_ELAPSED)
                from affilabs.core.experiment_clock import TimeBase
                display_val = timeline.stop_cursor.value()
                end_sensorgram_time = self.clock.convert(
                    display_val, TimeBase.DISPLAY, TimeBase.RAW_ELAPSED
                )

        self._current_cycle.complete(end_time_sensorgram=end_sensorgram_time or 0.0)
        self._completed_cycles.append(self._current_cycle)

        # Advance method progress counter (for snapshot-based execution)
        if hasattr(self, 'queue_presenter') and self.queue_presenter.has_method_snapshot():
            self.queue_presenter.advance_method_progress()
            logger.debug("✓ Method progress advanced")

        # Export cycle data for recording and Edits table
        # Pass clock so times are converted from RAW_ELAPSED to RECORDING coords
        _clock = getattr(self, 'clock', None)
        cycle_export_data = self._current_cycle.to_export_dict(clock=_clock)

        # Save to Edits table
        if hasattr(self.main_window, 'edits_tab'):
            self.main_window.edits_tab.add_cycle(cycle_export_data)
            logger.info(f"✓ {cycle_export_data.get('type', 'cycle')} saved to Edits table")

        # Save to recording if active
        if self.recording_mgr.is_recording:
            self.recording_mgr.add_cycle(cycle_export_data)

        self._current_cycle = None
        self._cycle_end_time = None

        # QueueSummaryWidget auto-refreshes via queue_changed signal — no manual update needed

        # Check if we should continue with the next cycle or finish the run
        # Use method progress if available, otherwise fall back to segment_queue
        if hasattr(self, 'queue_presenter') and self.queue_presenter.has_method_snapshot():
            progress = self.queue_presenter.get_method_progress()
            original_len = len(self.queue_presenter.get_original_method())
            remaining = original_len - progress
        else:
            remaining = len(self.segment_queue)
        
        # Clear running cycle highlight from queue table
        if tbl := self._sidebar_widget('summary_table'):
            tbl.set_running_cycle(None)
        
        if remaining > 0:
            # More cycles to run - auto-start next
            next_cycle_type = self.segment_queue[0].type if self.segment_queue else "Unknown"
            logger.info(f"Auto-starting next cycle: {next_cycle_type} ({remaining} cycles remaining)")
            from PySide6.QtCore import QTimer
            QTimer.singleShot(1000, self._on_start_button_clicked)
        else:
            # Queue completed - show retrieve button and unlock
            logger.info("✓ Queue execution completed - all cycles finished")
            
            # Unlock the queue
            if hasattr(self, 'queue_presenter'):
                self.queue_presenter.unlock_queue()
            
            # Show retrieve method button
            if btn := self._sidebar_widget('retrieve_method_btn'):
                btn.setVisible(True)
                logger.debug("✓ Retrieve Method button shown")
            
            # Change Stop button back to Start
            self._set_start_button_to_start_mode()
            
            # Start auto-read cycle
            import time
            from affilabs.domain.cycle import Cycle
            autoread_cycle = Cycle(
                type="Auto-read",
                length_minutes=999 * 60,
                name="Auto-read",
                note="Automatic continuous monitoring after cycle queue completion",
                status="pending",
            )
            autoread_cycle._units = "RU"
            autoread_cycle._timestamp = time.time()
            self.segment_queue.append(autoread_cycle)
            logger.info("Auto-read cycle created and queued")
            from PySide6.QtCore import QTimer
            QTimer.singleShot(1000, self._on_start_button_clicked)

    def _clear_all_cycle_markers(self):
        """Remove all cycle markers from the Full Sensorgram timeline."""
        try:
            if not hasattr(self.main_window, 'full_timeline_graph'):
                return
            timeline = self.main_window.full_timeline_graph
            for cycle_id, marker_data in self._cycle_markers.items():
                try:
                    if 'line' in marker_data:
                        timeline.removeItem(marker_data['line'])
                    if 'label' in marker_data:
                        timeline.removeItem(marker_data['label'])
                except Exception as e:
                    logger.debug(f"Could not remove cycle marker {cycle_id}: {e}")
            self._cycle_markers.clear()
        except Exception as e:
            logger.debug(f"_clear_all_cycle_markers error: {e}")

    # ------------------------------------------------------------------ #
    # Queue table context menu + helpers                                   #
    # ------------------------------------------------------------------ #

    def _renumber_cycles(self):
        """Renumber all cycles in queue to maintain sequential numbering."""
        for i, cycle in enumerate(self.segment_queue):
            cycle.name = f"Cycle {i + 1}"
            if hasattr(cycle, 'cycle_num'):
                cycle.cycle_num = i + 1

    def _update_summary_table(self):
        """Update summary table with first 5 cycles from segment queue."""
        from PySide6.QtGui import QColor
        from PySide6.QtWidgets import QTableWidgetItem
        from PySide6.QtCore import Qt

        table = self.main_window.sidebar.summary_table
        table.blockSignals(True)

        type_colors = {
            "Auto-read": QColor(242, 242, 247),
            "Baseline": QColor(217, 234, 250),
            "Immobilization": QColor(232, 245, 233),
            "Binding": QColor(255, 243, 224),
            "Kinetic": QColor(224, 237, 255),
            "Concentration": QColor(255, 243, 224),
        }

        recent_segments = self.segment_queue[:5]
        for row in range(5):
            if row < len(recent_segments):
                segment = recent_segments[row]
                status = getattr(segment, 'status', 'pending')
                if status == "pending":
                    state_text, state_color = "Queued", QColor(255, 249, 196)
                elif status == "active":
                    state_text, state_color = "Running", QColor(217, 234, 250)
                elif status == "completed":
                    state_text, state_color = "Done", QColor(232, 245, 233)
                else:
                    state_text, state_color = "-", QColor(242, 242, 247)

                def _item(text, color):
                    it = QTableWidgetItem(text)
                    it.setBackground(color)
                    return it

                table.setItem(row, 0, _item(state_text, state_color))
                cycle_type = getattr(segment, 'type', '')
                table.setItem(row, 1, _item(cycle_type, type_colors.get(cycle_type, QColor(242, 242, 247))))
                sensorgram_time = getattr(segment, 'sensorgram_time', None)
                start_time = f"{sensorgram_time:.1f}s" if sensorgram_time is not None else "--"
                table.setItem(row, 2, _item(start_time, state_color))
                note = getattr(segment, 'note', '')
                note_display = note[:40] + "..." if len(note) > 40 else note
                note_item = _item(note_display, state_color)
                note_item.setFlags(note_item.flags() | Qt.ItemFlag.ItemIsEditable)
                note_item.setToolTip(note or "Click to edit note")
                note_item.setData(Qt.ItemDataRole.UserRole, row)
                table.setItem(row, 3, note_item)
            else:
                for col in range(4):
                    empty = QTableWidgetItem("")
                    empty.setBackground(QColor(255, 255, 255))
                    table.setItem(row, col, empty)

        table.blockSignals(False)

    def _on_queue_table_context_menu(self, position):
        """Show context menu for queue table (right-click to delete cycles)."""
        from PySide6.QtWidgets import QMenu, QMessageBox
        from PySide6.QtGui import QAction

        table = self.main_window.sidebar.summary_table
        row = table.rowAt(position.y())

        if row < 0 or row >= table.rowCount():
            return
        if row >= len(self.segment_queue):
            QMessageBox.information(self.main_window, "No Cycle", "This row is empty.")
            return
        state_item = table.item(row, 0)
        if not state_item or not state_item.text():
            QMessageBox.information(self.main_window, "No Cycle", "This row is empty.")
            return

        menu = QMenu(table)
        cycle = self.segment_queue[row]
        delete_action = QAction(f"Delete '{cycle.name}'", table)
        delete_action.triggered.connect(lambda: self._delete_cycle_from_queue(row))
        menu.addAction(delete_action)
        menu.exec(table.viewport().mapToGlobal(position))

    def _delete_cycle_from_queue(self, row_index: int):
        """Delete a cycle from the queue by row index."""
        if row_index < 0 or row_index >= len(self.segment_queue):
            return
        cycle = self.segment_queue[row_index]
        cycle_name = cycle.name
        del self.segment_queue[row_index]
        self._renumber_cycles()
        logger.info(f"Deleted cycle from queue: {cycle_name}")
        if hasattr(self.main_window.sidebar, "intel_message_label"):
            remaining = len(self.segment_queue)
            self.main_window.sidebar.intel_message_label.setText(
                f"Deleted {cycle_name} ({remaining} {'cycle' if remaining == 1 else 'cycles'} remaining)"
            )
        self._update_summary_table()

    def _on_start_queued_run(self):
        """Start executing queued cycles (triggered by sidebar queued_run_started signal)."""
        self._on_start_button_clicked()

    def _on_next_cycle(self):
        """Skip to next cycle in queue (triggered by sidebar next_cycle_requested signal)."""
        if not self._current_cycle:
            logger.debug("Next Cycle: no active cycle, ignoring")
            return
        # Stop the cycle end timer so it doesn't fire again after the new cycle starts
        if hasattr(self, '_cycle_end_timer') and self._cycle_end_timer.isActive():
            self._cycle_end_timer.stop()
            logger.debug("✓ Cycle end timer stopped (Next Cycle pressed early)")
        self._on_cycle_completed()
