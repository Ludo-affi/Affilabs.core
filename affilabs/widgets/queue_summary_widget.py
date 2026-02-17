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
from PySide6.QtCore import Qt, Signal, Slot
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
    COL_NOTES = 3

    def __init__(self, parent=None):
        """Initialize queue summary table."""
        super().__init__(parent)

        self._presenter: Optional[QueuePresenter] = None
        self._is_locked = False
        self._running_cycle_id: Optional[str] = None  # Track which cycle is running

        self._setup_ui()
        self._setup_drag_drop()
        self._setup_empty_state()

        logger.debug("QueueSummaryWidget initialized")

    def _setup_ui(self):
        """Configure table appearance and behavior."""
        # Set columns
        self.setColumnCount(4)
        self.setHorizontalHeaderLabels(["#", "Type", "Duration (min)", "Notes"])

        # Column sizing - fit content for short columns, stretch Notes
        header = self.horizontalHeader()
        header.setSectionResizeMode(self.COL_NUM, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_TYPE, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_DURATION, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_NOTES, QHeaderView.ResizeMode.Stretch)

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

        # Connect presenter signals
        presenter.queue_changed.connect(self.refresh)
        presenter.queue_locked.connect(self._on_queue_locked)
        presenter.queue_unlocked.connect(self._on_queue_unlocked)

        logger.debug("QueueSummaryWidget connected to presenter")

    @Slot()
    def refresh(self):
        """Refresh table from presenter's queue state."""
        if not self._presenter:
            return

        # Save selection
        selected_rows = [item.row() for item in self.selectedItems()]

        # Block signals during bulk update to avoid flicker
        self.blockSignals(True)
        try:
            # Clear and repopulate
            self.setRowCount(0)

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
            for row in range(self.rowCount()):
                for col in range(self.columnCount()):
                    item = self.item(row, col)
                    if item:
                        item.setBackground(QBrush(QColor(235, 235, 235)))

        # Show/hide empty state
        if hasattr(self, '_empty_overlay'):
            self._empty_overlay.setVisible(self.rowCount() == 0)

        # Force visual repaint and scroll to bottom so new rows are visible
        self.viewport().update()
        if self.rowCount() > 0:
            self.scrollToBottom()

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
            num_item.setBackground(QBrush(QColor("#E3F2FD")))  # Light blue for running
        elif bg_color:
            num_item.setBackground(QBrush(QColor(bg_color)))
        self.setItem(row, self.COL_NUM, num_item)

        # Column 1: Type (color-coded abbreviation)
        type_item = QTableWidgetItem(abbr)
        type_item.setForeground(QColor(fg_color))
        type_item.setToolTip(cycle.type)
        type_item.setFlags(type_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        if is_running:
            type_item.setBackground(QBrush(QColor("#E3F2FD")))
        elif bg_color:
            type_item.setBackground(QBrush(QColor(bg_color)))
        self.setItem(row, self.COL_TYPE, type_item)

        # Column 2: Duration
        duration_item = QTableWidgetItem(f"{cycle.length_minutes:.1f}")
        duration_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        duration_item.setFlags(duration_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        if is_running:
            duration_item.setBackground(QBrush(QColor("#E3F2FD")))
        elif bg_color:
            duration_item.setBackground(QBrush(QColor(bg_color)))
        self.setItem(row, self.COL_DURATION, duration_item)

        # Column 3: Notes
        notes_item = QTableWidgetItem(cycle.note or "")
        notes_item.setFlags(notes_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        if is_running:
            notes_item.setBackground(QBrush(QColor("#E3F2FD")))
        elif bg_color:
            notes_item.setBackground(QBrush(QColor(bg_color)))
        self.setItem(row, self.COL_NOTES, notes_item)

        # Store cycle ID in row data
        self.item(row, 0).setData(Qt.ItemDataRole.UserRole, cycle.cycle_id)

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

        Args:
            cycle_id: ID of running cycle, or None to clear
        """
        self._running_cycle_id = cycle_id
        self.refresh()  # Refresh to show running indicator

    # ========================================================================
    # DRAG-DROP IMPLEMENTATION
    # ========================================================================

    def dropEvent(self, event):
        """Handle drop event for reordering.

        Args:
            event: QDropEvent
        """
        if self._is_locked:
            event.ignore()
            return

        # Get source and destination rows
        source_row = self.currentRow()
        drop_row = self.indexAt(event.pos()).row()

        if source_row < 0 or drop_row < 0:
            event.ignore()
            return

        # Accept the drop
        event.accept()

        # Emit signal for presenter to handle
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

    def get_cycle_count(self) -> int:
        """Get number of cycles in table.

        Returns:
            Row count
        """
        return self.rowCount()

    def clear_selection(self):
        """Clear all selection."""
        self.clearSelection()
