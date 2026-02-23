"""Queue Summary Widget - Table display for queued cycles with drag-drop.

ARCHITECTURE LAYER: UI Widget (Phase 4)

This widget displays the queue table with:
- Drag-and-drop reordering
- Multi-select for bulk operations
- Context menu (delete, duplicate)
- Visual feedback for locked state

FEATURES:
- Internal drag-drop reordering
- Selection highlighting
- Read-only when queue is locked
- Custom rendering for cycle info

USAGE:
    # Create widget
    widget = QueueSummaryWidget()

    # Connect to presenter
    widget.cycle_reordered.connect(presenter.reorder_cycle)
    widget.cycles_deleted.connect(presenter.delete_cycles)
    presenter.queue_changed.connect(widget.refresh_from_presenter)

    # Populate
    widget.set_presenter(presenter)
    widget.refresh()
"""

from typing import List, Optional
from PySide6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMenu, QLabel
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtGui import QColor, QBrush

from affilabs.domain.cycle import Cycle
from affilabs.presenters.queue_presenter import QueuePresenter
from affilabs.utils.logger import logger
from affilabs.widgets.ui_constants import CycleTypeStyle


class QueueSummaryWidget(QTableWidget):
    """Table widget for displaying and managing cycle queue.

    Features:
    - Drag-and-drop reordering (internal only)
    - Multi-selection for bulk delete
    - Context menu
    - Visual locked state

    Signals:
        cycle_reordered: User dragged cycle (from_index, to_index)
        cycles_deleted: User deleted cycles (indices list)
        selection_changed: Selection changed (indices list)
    """

    # Signals
    cycle_reordered = Signal(int, int)  # from_index, to_index
    cycles_deleted = Signal(list)  # List of indices
    selection_changed = Signal(list)  # List of selected indices

    # Column indices
    COL_NUM = 0
    COL_TYPE = 1
    COL_DURATION = 2
    COL_STATUS = 3

    def __init__(self, parent=None):
        """Initialize queue summary table."""
        super().__init__(parent)

        self._presenter: Optional[QueuePresenter] = None
        self._is_locked = False
        self._running_cycle_id: Optional[str] = None  # Track which cycle is running
        self._refresh_pending = False  # Debounce guard
        self._cycles_in_edits: set = set()  # cycle_ids sent to Edits tab

        self._setup_ui()
        self._setup_drag_drop()
        self._setup_empty_state()

        logger.debug("QueueSummaryWidget initialized")

    def _setup_ui(self):
        """Configure table appearance and behavior."""
        # Set columns
        self.setColumnCount(4)
        self.setHorizontalHeaderLabels(["#", "Type", "Duration (min)", "Status"])

        # Column sizing - fit content for all columns, stretch Status
        header = self.horizontalHeader()
        header.setSectionResizeMode(self.COL_NUM, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_TYPE, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_DURATION, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_STATUS, QHeaderView.ResizeMode.Stretch)

        # Scroll settings - critical for nested-inside-QScrollArea to work
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

        # Selection behavior
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

        # Visual style
        self.setAlternatingRowColors(False)  # We handle colors manually
        self.setShowGrid(True)

        # Context menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        # Selection tracking
        self.itemSelectionChanged.connect(self._on_selection_changed)

    def _setup_drag_drop(self):
        """Configure drag-and-drop reordering."""
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

    def _setup_empty_state(self):
        """Create empty state overlay."""
        self._empty_overlay = QLabel(self)
        self._empty_overlay.setText(
            "📭\n\n"
            "No cycles in queue\n\n"
            "Click 'Build Method' to add cycles"
        )
        self._empty_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_overlay.setStyleSheet(
            "QLabel {"
            "  color: #86868B;"
            "  font-size: 13px;"
            "  font-weight: 500;"
            "  background: transparent;"
            "  padding: 40px;"
            "}"
        )
        self._empty_overlay.setVisible(False)  # Hidden by default
        self._empty_overlay.raise_()

    def resizeEvent(self, event):
        """Keep empty overlay centered."""
        super().resizeEvent(event)
        if hasattr(self, '_empty_overlay'):
            self._empty_overlay.setGeometry(self.viewport().rect())

    def wheelEvent(self, event):
        """Handle wheel events — keep scroll inside the table.

        Prevents mouse-wheel events from leaking to the parent QScrollArea
        when this QTableWidget still has room to scroll in the requested
        direction.
        """
        sb = self.verticalScrollBar()
        if sb and sb.isVisible():
            # Table has overflow → handle scroll internally
            super().wheelEvent(event)
            event.accept()
        else:
            # No overflow → let the sidebar scroll
            event.ignore()

    # ========================================================================
    # PUBLIC API - Presenter Integration
    # ========================================================================

    def set_presenter(self, presenter: QueuePresenter):
        """Connect to queue presenter.

        Args:
            presenter: QueuePresenter instance
        """
        self._presenter = presenter

        # Connect presenter signals — queue_changed goes through debounce so
        # multiple signals fired in the same event-loop tick (advance_method_progress,
        # lock_queue, set_running_cycle) collapse into a single table rebuild.
        presenter.queue_changed.connect(self._schedule_refresh)
        presenter.queue_locked.connect(self._on_queue_locked)
        presenter.queue_unlocked.connect(self._on_queue_unlocked)

        logger.debug("QueueSummaryWidget connected to presenter")

    def _schedule_refresh(self):
        """Debounce entry-point: schedules one refresh per event-loop tick.

        Multiple same-tick signals (advance_method_progress → queue_changed,
        lock_queue → queue_locked, set_running_cycle) each call this.  Only
        the *first* call in any given tick schedules the actual rebuild; the
        rest are no-ops because _refresh_pending is already True.
        """
        if not self._refresh_pending:
            self._refresh_pending = True
            QTimer.singleShot(0, self._do_refresh)

    def _do_refresh(self):
        """Actual rebuild — called once per debounced batch."""
        self._refresh_pending = False
        self.refresh()

    @Slot()
    def refresh(self):
        """Refresh table from presenter's queue state.

        During execution (locked + snapshot exists): shows the full original
        method with completed/running/pending indicators so the user can
        always see the entire plan.

        Otherwise: shows the live queue as before.
        """
        if not self._presenter:
            return

        # Save selection
        selected_rows = [item.row() for item in self.selectedItems()]

        # Hide empty overlay during rebuild to avoid blank flash
        if hasattr(self, '_empty_overlay'):
            self._empty_overlay.setVisible(False)

        # Block signals during bulk update to avoid flicker
        self.blockSignals(True)
        try:
            self.setRowCount(0)

            # Decide display mode
            if self._is_locked and self._presenter.has_method_snapshot():
                # EXECUTION MODE: show full original method with progress
                original = self._presenter.get_original_method()
                progress = self._presenter.get_method_progress()
                for row, cycle in enumerate(original):
                    if row < progress:
                        self._add_cycle_row_with_status(row, cycle, "completed")
                    elif row == progress:
                        self._add_cycle_row_with_status(row, cycle, "running")
                    else:
                        self._add_cycle_row_with_status(row, cycle, "pending")
            elif self._presenter.has_method_snapshot() and not self._is_locked:
                # POST-RUN: snapshot still exists after unlock (cancelled or finished)
                # Show full method with all progress so user can retrieve it
                original = self._presenter.get_original_method()
                progress = self._presenter.get_method_progress()
                for row, cycle in enumerate(original):
                    if row < progress:
                        self._add_cycle_row_with_status(row, cycle, "completed")
                    else:
                        self._add_cycle_row_with_status(row, cycle, "pending")
            else:
                # NORMAL MODE: show live queue
                cycles = self._presenter.get_queue_snapshot()
                for row, cycle in enumerate(cycles):
                    self._add_cycle_row(row, cycle)
        finally:
            self.blockSignals(False)

        # Restore selection (if rows still exist)
        for row in selected_rows:
            if row < self.rowCount():
                self.selectRow(row)

        # Enforce lock visuals if queue is currently locked
        if self._is_locked:
            self.setDragEnabled(False)
            self.setAcceptDrops(False)

        # Show/hide empty state
        if hasattr(self, '_empty_overlay'):
            self._empty_overlay.setVisible(self.rowCount() == 0)

        # Force visual repaint; scroll to running row if visible
        self.viewport().update()
        running_row = self._find_running_row()
        if running_row >= 0:
            self.scrollTo(self.model().index(running_row, 0))
        elif self.rowCount() > 0:
            self.scrollToBottom()

    def _find_running_row(self) -> int:
        """Find the row index of the currently running cycle.

        Returns:
            Row index, or -1 if no cycle is running
        """
        if not self._presenter or not self._presenter.has_method_snapshot():
            return -1
        return self._presenter.get_method_progress()  # running row == progress index

    def _add_cycle_row_with_status(self, row: int, cycle: Cycle, status: str):
        """Add a row with execution status styling.

        Args:
            row: Row index
            cycle: Cycle to display
            status: "completed", "running", or "pending"
        """
        self.insertRow(row)
        abbr, fg_color = CycleTypeStyle.get(cycle.type)

        if status == "running":
            prefix, bg = "", QColor("#1565C0")   # Solid blue background (no arrow)
            bold = True
            fg_color = "#FFFFFF"
        elif status == "completed":
            prefix, bg = "", QColor("#E8F5E9")    # light green, bold
            bold = True
            fg_color = "#4CAF50"
        else:
            prefix, bg = "", None
            bold = False

        cycle_num = cycle.cycle_num if cycle.cycle_num > 0 else row + 1

        status_text = self._status_label(cycle.cycle_id, status)
        for col, (text, align) in enumerate([
            (str(cycle_num), Qt.AlignmentFlag.AlignCenter),
            (f"{prefix}{abbr}", None),
            (f"{cycle.length_minutes:.1f}", Qt.AlignmentFlag.AlignCenter),
            (status_text, Qt.AlignmentFlag.AlignCenter),
        ]):
            item = QTableWidgetItem(text)
            if align:
                item.setTextAlignment(align)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if col == 1:
                item.setForeground(QColor(fg_color))
                item.setToolTip(f"{cycle.type} ({status})")
            elif status == "running":
                item.setForeground(QColor("#FFFFFF"))
            if bg:
                item.setBackground(QBrush(bg))
            if bold:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            self.setItem(row, col, item)

        self.item(row, 0).setData(Qt.ItemDataRole.UserRole, cycle.cycle_id)

    def _add_cycle_row(self, row: int, cycle: Cycle):
        """Add a row for a cycle.

        Args:
            row: Row index
            cycle: Cycle to display
        """
        self.insertRow(row)

        # Get type color and background
        abbr, fg_color = CycleTypeStyle.get(cycle.type)
        bg_color = self._get_type_background(cycle.type)
        is_running = (self._running_cycle_id and cycle.cycle_id == self._running_cycle_id)

        # Column 0: Cycle number
        cycle_num = cycle.cycle_num if cycle.cycle_num > 0 else row + 1
        num_item = QTableWidgetItem(str(cycle_num))
        num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        num_item.setFlags(num_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        if is_running:
            num_item.setBackground(QBrush(QColor("#1565C0")))  # Solid blue for running
            num_item.setForeground(QColor("#FFFFFF"))  # White text
            font = num_item.font()
            font.setBold(True)
            num_item.setFont(font)
        elif bg_color:
            num_item.setBackground(QBrush(QColor(bg_color)))
        self.setItem(row, self.COL_NUM, num_item)

        # Column 1: Type (color-coded abbreviation)
        type_item = QTableWidgetItem(abbr)
        type_item.setToolTip(cycle.type)
        type_item.setFlags(type_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        if is_running:
            type_item.setBackground(QBrush(QColor("#1565C0")))
            type_item.setForeground(QColor("#FFFFFF"))  # White text
            font = type_item.font()
            font.setBold(True)
            type_item.setFont(font)
        else:
            type_item.setForeground(QColor(fg_color))
            if bg_color:
                type_item.setBackground(QBrush(QColor(bg_color)))
        self.setItem(row, self.COL_TYPE, type_item)

        # Column 2: Duration
        duration_item = QTableWidgetItem(f"{cycle.length_minutes:.1f}")
        duration_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        duration_item.setFlags(duration_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        if is_running:
            duration_item.setBackground(QBrush(QColor("#1565C0")))
            duration_item.setForeground(QColor("#FFFFFF"))  # White text
            font = duration_item.font()
            font.setBold(True)
            duration_item.setFont(font)
        elif bg_color:
            duration_item.setBackground(QBrush(QColor(bg_color)))
        self.setItem(row, self.COL_DURATION, duration_item)

        # Column 3: Status
        raw_status = "running" if is_running else "pending"
        status_text = self._status_label(cycle.cycle_id, raw_status)
        status_item = QTableWidgetItem(status_text)
        status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        if cycle.note:
            status_item.setToolTip(cycle.note)
        if is_running:
            status_item.setBackground(QBrush(QColor("#1565C0")))
            status_item.setForeground(QColor("#FFFFFF"))
            font = status_item.font()
            font.setBold(True)
            status_item.setFont(font)
        elif bg_color:
            status_item.setBackground(QBrush(QColor(bg_color)))
        self.setItem(row, self.COL_STATUS, status_item)

        # Store cycle ID in row data
        self.item(row, 0).setData(Qt.ItemDataRole.UserRole, cycle.cycle_id)

    def _status_label(self, cycle_id: int, execution_status: str) -> str:
        """Return display text for the Status column.

        Args:
            cycle_id: Cycle's permanent ID
            execution_status: 'pending', 'running', or 'completed'
        """
        if cycle_id in self._cycles_in_edits:
            return "In Edits"
        if execution_status == "running":
            return "Running"
        if execution_status == "completed":
            return "Done"
        return "Pending"

    def mark_in_edits(self, cycle_id: int) -> None:
        """Mark a cycle as having been sent to the Edits tab.

        Called by _cycle_mixin after edits_tab.add_cycle() succeeds.
        Schedules a debounced refresh so the Status column updates.
        """
        self._cycles_in_edits.add(cycle_id)
        self._schedule_refresh()

    def _get_type_background(self, cycle_type: str) -> Optional[str]:
        """Get subtle background color for cycle type.

        Args:
            cycle_type: Cycle type name

        Returns:
            Hex color string or None
        """
        type_lower = cycle_type.lower()
        if 'baseline' in type_lower:
            return '#F0F4FF'  # Subtle blue
        elif 'binding' in type_lower:
            return '#FFFEF0'  # Subtle yellow (manual injection / incubation)
        elif 'kinetic' in type_lower or 'association' in type_lower:
            return '#F0FFF4'  # Subtle green (flow / on+off rate)
        elif 'dissociation' in type_lower:
            return '#FFF4F0'  # Subtle orange
        elif 'regeneration' in type_lower:
            return '#FFF0F5'  # Subtle pink
        elif 'concentration' in type_lower:
            return '#FFFEF0'  # Legacy alias for Binding
        return None  # No background for other types

    def _abbreviate_type(self, cycle_type: str) -> str:
        """Abbreviate cycle type for compact display.

        Args:
            cycle_type: Full cycle type name

        Returns:
            Abbreviated type (e.g. '● BL')
        """
        abbr, _ = CycleTypeStyle.get(cycle_type)
        return abbr

    def set_running_cycle(self, cycle_id: Optional[str]):
        """Mark a cycle as currently running.

        Updates _running_cycle_id and schedules a debounced refresh so this
        call (which comes right after advance_method_progress and lock_queue
        have both already scheduled their own refreshes) is folded into the
        same single rebuild rather than triggering an additional one.

        Args:
            cycle_id: ID of running cycle, or None to clear
        """
        self._running_cycle_id = cycle_id
        self._schedule_refresh()

    # ========================================================================
    # DRAG-DROP IMPLEMENTATION
    # ========================================================================

    def dropEvent(self, event):
        """Handle drop event for reordering.

        We deliberately do NOT call super().dropEvent() — Qt's InternalMove
        would delete the source row before the presenter can reorder the data,
        causing the cycle to disappear.  Instead we capture row indices, ignore
        Qt's built-in move, and let the presenter rebuild the table via refresh().

        Args:
            event: QDropEvent
        """
        if self._is_locked:
            event.ignore()
            return

        source_row = self.currentRow()
        drop_index = self.indexAt(event.position().toPoint())
        drop_row = drop_index.row()

        # If dropped below all rows, target the last row
        if drop_row < 0:
            drop_row = self.rowCount() - 1

        if source_row < 0 or source_row == drop_row:
            event.ignore()
            return

        # Suppress Qt's built-in move (would remove the row before presenter acts)
        event.setDropAction(Qt.DropAction.IgnoreAction)
        event.accept()

        # Let presenter reorder and refresh the table
        self.cycle_reordered.emit(source_row, drop_row)

        logger.debug(f"Drag-drop: row {source_row} → {drop_row}")

    def dragEnterEvent(self, event):
        """Handle drag enter.

        Args:
            event: QDragEnterEvent
        """
        if not self._is_locked:
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        """Handle drag move.

        Args:
            event: QDragMoveEvent
        """
        if not self._is_locked:
            event.accept()
        else:
            event.ignore()

    # ========================================================================
    # SELECTION & CONTEXT MENU
    # ========================================================================

    def _on_selection_changed(self):
        """Handle selection change."""
        selected_indices = self.get_selected_indices()
        self.selection_changed.emit(selected_indices)

    def get_selected_indices(self) -> List[int]:
        """Get list of selected row indices.

        Returns:
            List of selected row indices (sorted)
        """
        rows = set(item.row() for item in self.selectedItems())
        return sorted(rows)

    def _show_context_menu(self, pos):
        """Show context menu on right-click.

        Args:
            pos: Mouse position
        """
        if self._is_locked:
            return

        menu = QMenu(self)

        # Delete action
        delete_action = menu.addAction("Delete Selected")
        delete_action.triggered.connect(self._delete_selected)

        # Only show if items are selected
        if not self.selectedItems():
            delete_action.setEnabled(False)

        menu.exec(self.viewport().mapToGlobal(pos))

    def _delete_selected(self):
        """Delete selected cycles."""
        indices = self.get_selected_indices()
        if indices:
            self.cycles_deleted.emit(indices)

    # ========================================================================
    # LOCK STATE MANAGEMENT
    # ========================================================================

    @Slot()
    def _on_queue_locked(self):
        """Handle queue locked signal.

        Disables editing (drag-drop, context-menu delete) while keeping
        the table scrollable and clickable so users can inspect the queue
        during a run.
        """
        self._is_locked = True

        # Disable drag-drop reordering only — keep widget enabled for scrolling
        self.setDragEnabled(False)
        self.setAcceptDrops(False)

        # Visual feedback: subtle gray background so user knows edits are locked
        for row in range(self.rowCount()):
            for col in range(self.columnCount()):
                item = self.item(row, col)
                if item:
                    item.setBackground(QBrush(QColor(235, 235, 235)))

        logger.debug("Queue table locked (read-only, scrollable)")

    @Slot()
    def _on_queue_unlocked(self):
        """Handle queue unlocked signal."""
        self._is_locked = False

        # Re-enable drag-drop reordering
        self.setDragEnabled(True)
        self.setAcceptDrops(True)

        # Restore normal appearance
        for row in range(self.rowCount()):
            for col in range(self.columnCount()):
                item = self.item(row, col)
                if item:
                    item.setBackground(QBrush(Qt.GlobalColor.white))

        logger.debug("Queue table unlocked")

    # ========================================================================
    # UTILITY METHODS
    # ========================================================================

    def show_method_complete(self) -> None:
        """Append a 'Method Complete' footer row at the bottom of the table."""
        row = self.rowCount()
        self.insertRow(row)
        item = QTableWidgetItem("✓  Method Complete")
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)  # not selectable/editable
        item.setForeground(QBrush(QColor("#34C759")))
        item.setBackground(QBrush(QColor("#F0FFF4")))
        from PySide6.QtGui import QFont
        font = QFont()
        font.setBold(True)
        font.setPointSize(10)
        item.setFont(font)
        self.setItem(row, 0, item)
        # Span all 4 columns
        self.setSpan(row, 0, 1, self.columnCount())
        self.scrollToBottom()
        self._completion_row = row

    def clear_method_complete(self) -> None:
        """Remove the completion footer row if present."""
        if hasattr(self, '_completion_row') and self._completion_row < self.rowCount():
            self.removeRow(self._completion_row)
            self._completion_row = -1
            self.clearSpans()

    def get_cycle_count(self) -> int:
        """Get number of cycles in table.

        Returns:
            Row count
        """
        return self.rowCount()

    def clear_selection(self):
        """Clear all selection."""
        self.clearSelection()
