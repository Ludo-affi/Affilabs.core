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
    QMenu
)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QColor, QBrush

from affilabs.domain.cycle import Cycle
from affilabs.presenters.queue_presenter import QueuePresenter
from affilabs.utils.logger import logger


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

        self._setup_ui()
        self._setup_drag_drop()

        logger.debug("QueueSummaryWidget initialized")

    def _setup_ui(self):
        """Configure table appearance and behavior."""
        # Set columns
        self.setColumnCount(4)
        self.setHorizontalHeaderLabels(["#", "Type", "Duration (min)", "Notes"])

        # Column sizing
        header = self.horizontalHeader()
        header.setSectionResizeMode(self.COL_NUM, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_TYPE, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(self.COL_DURATION, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_NOTES, QHeaderView.ResizeMode.Stretch)

        # Selection behavior
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

        # Visual style
        self.setAlternatingRowColors(True)
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

        # Clear and repopulate
        self.setRowCount(0)

        cycles = self._presenter.get_queue_snapshot()

        for row, cycle in enumerate(cycles):
            self._add_cycle_row(row, cycle)

        # Restore selection (if rows still exist)
        for row in selected_rows:
            if row < self.rowCount():
                self.selectRow(row)

        # Update enabled state
        self.setEnabled(not self._is_locked)

    def _add_cycle_row(self, row: int, cycle: Cycle):
        """Add a row for a cycle.

        Args:
            row: Row index
            cycle: Cycle to display
        """
        self.insertRow(row)

        # Column 0: Cycle number (use cycle_num if available, otherwise row+1)
        cycle_num = cycle.cycle_num if cycle.cycle_num > 0 else row + 1
        num_item = QTableWidgetItem(str(cycle_num))
        num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        num_item.setFlags(num_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.setItem(row, self.COL_NUM, num_item)

        # Column 1: Type
        type_item = QTableWidgetItem(self._abbreviate_type(cycle.type))
        type_item.setFlags(type_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.setItem(row, self.COL_TYPE, type_item)

        # Column 2: Duration
        duration_item = QTableWidgetItem(f"{cycle.length_minutes:.1f}")
        duration_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        duration_item.setFlags(duration_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.setItem(row, self.COL_DURATION, duration_item)

        # Column 3: Notes
        notes_item = QTableWidgetItem(cycle.note or "")
        notes_item.setFlags(notes_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.setItem(row, self.COL_NOTES, notes_item)

        # Store cycle ID in row data
        self.item(row, 0).setData(Qt.ItemDataRole.UserRole, cycle.cycle_id)

    def _abbreviate_type(self, cycle_type: str) -> str:
        """Abbreviate cycle type for compact display.

        Args:
            cycle_type: Full cycle type name

        Returns:
            Abbreviated type
        """
        abbreviations = {
            "Baseline": "Base",
            "Association": "Assoc",
            "Dissociation": "Dissoc",
            "Regeneration": "Regen",
            "Custom": "Custom"
        }
        return abbreviations.get(cycle_type, cycle_type[:6])

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
        """Handle queue locked signal."""
        self._is_locked = True
        self.setEnabled(False)

        # Visual feedback: gray out all rows
        for row in range(self.rowCount()):
            for col in range(self.columnCount()):
                item = self.item(row, col)
                if item:
                    item.setBackground(QBrush(QColor(220, 220, 220)))

        logger.debug("Queue table locked")

    @Slot()
    def _on_queue_unlocked(self):
        """Handle queue unlocked signal."""
        self._is_locked = False
        self.setEnabled(True)

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
