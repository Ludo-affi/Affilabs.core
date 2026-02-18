"""Queue Presenter - Coordination layer for queue management.

ARCHITECTURE LAYER: Presenter (MVP pattern)

This presenter coordinates between:
- QueueManager (state/business logic)
- CommandHistory (undo/redo)
- UI components (views)

RESPONSIBILITIES:
- Wrap queue operations in undoable commands
- Execute operations through CommandHistory
- Forward signals from QueueManager to UI
- Provide high-level API for UI interactions
- Handle keyboard shortcuts (Ctrl+Z, Ctrl+Shift+Z)

BENEFITS:
- Clean separation of concerns
- All queue ops are undoable by default
- UI doesn't know about Command pattern
- Easy to test (mock QueueManager/History)
- Single source of truth for queue state

USAGE:
    # Initialize presenter
    presenter = QueuePresenter()

    # Connect to UI
    presenter.queue_changed.connect(update_table)
    presenter.can_undo_changed.connect(update_undo_button)

    # User adds cycle
    presenter.add_cycle(cycle)

    # User presses Ctrl+Z
    presenter.undo()

    # User presses Ctrl+Shift+Z
    presenter.redo()
"""

from typing import List, Optional
from PySide6.QtCore import QObject, Signal, Slot

from affilabs.domain.cycle import Cycle
from affilabs.managers.queue_manager import QueueManager
from affilabs.managers.command_history import (
    CommandHistory,
    AddCycleCommand,
    DeleteCycleCommand,
    DeleteCyclesCommand,
    ReorderCycleCommand,
    ClearQueueCommand
)
from affilabs.utils.logger import logger


class QueuePresenter(QObject):
    """Presenter for queue management - coordinates state, history, and UI.

    This class sits between the QueueManager (model) and UI (view), implementing
    the MVP pattern. All queue operations go through CommandHistory for undo/redo.

    Signals:
        queue_changed: Queue state changed (add/delete/reorder/clear)
        cycle_added: New cycle added to queue
        cycle_deleted: Cycle removed from queue
        cycle_reordered: Cycle moved to different position
        queue_locked: Queue locked (during execution)
        queue_unlocked: Queue unlocked (execution finished)
        can_undo_changed: Undo availability changed
        can_redo_changed: Redo availability changed
        undo_description_changed: Undo action description changed
        redo_description_changed: Redo action description changed
    """

    # Queue state signals (forwarded from QueueManager)
    queue_changed = Signal()
    cycle_added = Signal(Cycle)
    cycle_deleted = Signal(int, Cycle)  # index, cycle
    cycle_reordered = Signal(int, int)  # from_index, to_index
    queue_locked = Signal()
    queue_unlocked = Signal()

    # Undo/redo signals (forwarded from CommandHistory)
    can_undo_changed = Signal(bool)
    can_redo_changed = Signal(bool)
    undo_description_changed = Signal(str)  # Human-readable undo action
    redo_description_changed = Signal(str)  # Human-readable redo action

    def __init__(self, max_history: int = 50):
        """Initialize queue presenter.

        Args:
            max_history: Maximum undo history depth (default 50)
        """
        super().__init__()

        # Initialize components
        self._queue_manager = QueueManager()
        self._history = CommandHistory(max_history=max_history)

        # Pause state
        self._is_paused = False

        # Forward QueueManager signals to UI
        self._queue_manager.queue_changed.connect(self.queue_changed)
        self._queue_manager.cycle_added.connect(self.cycle_added)
        self._queue_manager.cycle_deleted.connect(self.cycle_deleted)
        self._queue_manager.cycle_reordered.connect(self.cycle_reordered)
        self._queue_manager.queue_locked.connect(self.queue_locked)
        self._queue_manager.queue_unlocked.connect(self.queue_unlocked)

        # Forward CommandHistory signals to UI
        self._history.can_undo_changed.connect(self.can_undo_changed)
        self._history.can_redo_changed.connect(self.can_redo_changed)
        self._history.history_changed.connect(self._on_history_changed)

        logger.debug("QueuePresenter initialized")

    # ========================================================================
    # PUBLIC API - Queue Operations (Undoable)
    # ========================================================================

    @Slot(Cycle)
    def add_cycle(self, cycle: Cycle) -> bool:
        """Add cycle to queue (undoable).

        Args:
            cycle: Cycle to add

        Returns:
            True if added successfully
        """
        cmd = AddCycleCommand(self._queue_manager, cycle)
        return self._history.execute(cmd)

    @Slot(int)
    def delete_cycle(self, index: int) -> bool:
        """Delete cycle at index (undoable).

        Args:
            index: Position in queue (0-based)

        Returns:
            True if deleted successfully
        """
        cmd = DeleteCycleCommand(self._queue_manager, index)
        return self._history.execute(cmd)

    @Slot(list)
    def delete_cycles(self, indices: List[int]) -> bool:
        """Delete multiple cycles at once (undoable).

        Args:
            indices: List of positions to delete

        Returns:
            True if deleted successfully
        """
        if not indices:
            return False

        cmd = DeleteCyclesCommand(self._queue_manager, indices)
        return self._history.execute(cmd)

    @Slot(int, int)
    def reorder_cycle(self, from_index: int, to_index: int) -> bool:
        """Move cycle from one position to another (undoable).

        Args:
            from_index: Source position
            to_index: Destination position

        Returns:
            True if reordered successfully
        """
        cmd = ReorderCycleCommand(self._queue_manager, from_index, to_index)
        return self._history.execute(cmd)

    @Slot()
    def clear_queue(self) -> bool:
        """Clear all cycles from queue (undoable).

        Returns:
            True if cleared successfully
        """
        cmd = ClearQueueCommand(self._queue_manager)
        return self._history.execute(cmd)

    # ========================================================================
    # PUBLIC API - Undo/Redo Operations
    # ========================================================================

    @Slot()
    def undo(self) -> bool:
        """Undo last operation.

        Returns:
            True if undo succeeded
        """
        return self._history.undo()

    @Slot()
    def redo(self) -> bool:
        """Redo last undone operation.

        Returns:
            True if redo succeeded
        """
        return self._history.redo()

    def can_undo(self) -> bool:
        """Check if undo is available.

        Returns:
            True if there are operations to undo
        """
        return self._history.can_undo()

    def can_redo(self) -> bool:
        """Check if redo is available.

        Returns:
            True if there are operations to redo
        """
        return self._history.can_redo()

    def get_undo_description(self) -> Optional[str]:
        """Get description of next undo action.

        Returns:
            Description string like "Add Baseline cycle", or None
        """
        return self._history.get_undo_description()

    def get_redo_description(self) -> Optional[str]:
        """Get description of next redo action.

        Returns:
            Description string, or None
        """
        return self._history.get_redo_description()

    # ========================================================================
    # PUBLIC API - Queue State Access (Read-Only)
    # ========================================================================

    def get_queue_size(self) -> int:
        """Get number of cycles in queue.

        Returns:
            Queue size
        """
        return self._queue_manager.get_queue_size()

    def get_queue_snapshot(self) -> List[Cycle]:
        """Get immutable copy of current queue.

        Returns:
            List of cycles in queue (copy)
        """
        return self._queue_manager.get_queue_snapshot()

    def get_completed_cycles(self) -> List[Cycle]:
        """Get list of completed cycles.

        Returns:
            List of completed cycles (copy)
        """
        return self._queue_manager.get_completed_cycles()

    def get_total_duration(self) -> float:
        """Get total duration of all queued cycles.

        Returns:
            Total duration in minutes
        """
        return self._queue_manager.get_total_duration()

    def find_cycle_by_id(self, cycle_id: int) -> Optional[Cycle]:
        """Find cycle by permanent ID.

        Args:
            cycle_id: Cycle ID to search for

        Returns:
            Cycle if found, None otherwise
        """
        return self._queue_manager.find_cycle_by_id(cycle_id)

    def peek_next_cycle(self) -> Optional[Cycle]:
        """Preview next cycle without removing it.

        Returns:
            Next cycle to execute, or None if queue empty
        """
        return self._queue_manager.peek_next_cycle()

    def is_queue_locked(self) -> bool:
        """Check if queue is locked.

        Returns:
            True if queue is locked (during execution)
        """
        return self._queue_manager.is_locked()

    # ========================================================================
    # PUBLIC API - Execution Control
    # ========================================================================

    def lock_queue(self):
        """Lock queue to prevent modifications during execution."""
        self._queue_manager.lock()
        logger.debug("Queue locked by presenter")

    def unlock_queue(self):
        """Unlock queue after execution completes."""
        self._queue_manager.unlock()
        logger.debug("Queue unlocked by presenter")

    def pop_next_cycle(self) -> Optional[Cycle]:
        """Remove and return next cycle for execution.

        This is NOT undoable - used for actual cycle execution.

        Returns:
            Next cycle, or None if queue empty
        """
        return self._queue_manager.pop_next_cycle()

    def mark_cycle_completed(self, cycle: Cycle):
        """Mark a cycle as completed.

        Args:
            cycle: Completed cycle to add to history
        """
        self._queue_manager.mark_completed(cycle)
        logger.debug(f"✅ Cycle {cycle.name} marked completed")

    # ========================================================================
    # PUBLIC API - State Persistence
    # ========================================================================

    def get_state(self) -> dict:
        """Get current state for backup/persistence.

        Returns:
            State dictionary with queue, completed, counter
        """
        return self._queue_manager.get_state()

    def restore_state(self, state: dict) -> bool:
        """Restore state from backup.

        Args:
            state: State dictionary from get_state()

        Returns:
            True if restored successfully
        """
        success = self._queue_manager.restore_state(state)
        if success:
            # Clear undo/redo history when restoring from backup
            self._history.clear()
            logger.info("State restored, undo/redo history cleared")
        return success

    def clear_history(self):
        """Clear undo/redo history.

        Use this when loading a new queue or after major state changes.
        """
        self._history.clear()
        logger.info("Undo/redo history cleared")

    # ========================================================================
    # PRIVATE - Event Handlers
    # ========================================================================

    def _on_history_changed(self):
        """Handle history state change - update undo/redo descriptions."""
        # Emit description changes for UI buttons/tooltips
        undo_desc = self.get_undo_description()
        redo_desc = self.get_redo_description()

        if undo_desc:
            self.undo_description_changed.emit(undo_desc)

        if redo_desc:
            self.redo_description_changed.emit(redo_desc)

    # ========================================================================
    # PAUSE/RESUME CONTROL
    # ========================================================================

    def pause_queue(self) -> None:
        """Pause queue execution after current cycle completes.

        This is a soft pause - it doesn't interrupt the current cycle,
        but prevents the next cycle from starting automatically.
        """
        self._is_paused = True
        logger.info("Queue paused (will stop after current cycle)")

    def resume_queue(self) -> None:
        """Resume queue execution from pause state."""
        self._is_paused = False
        logger.info("Queue resumed")

    def is_paused(self) -> bool:
        """Check if queue is paused.

        Returns:
            True if queue is paused, False otherwise
        """
        return self._is_paused

    # ========================================================================
    # DEBUGGING / STATS
    # ========================================================================

    def get_stats(self) -> dict:
        """Get presenter statistics for debugging.

        Returns:
            Dictionary with queue size, history counts, lock state
        """
        return {
            'queue_size': self.get_queue_size(),
            'completed_count': len(self.get_completed_cycles()),
            'total_duration_min': self.get_total_duration(),
            'undo_count': self._history.get_undo_count(),
            'redo_count': self._history.get_redo_count(),
            'is_locked': self.is_queue_locked(),
            'can_undo': self.can_undo(),
            'can_redo': self.can_redo()
        }

    def __repr__(self) -> str:
        """String representation for debugging."""
        stats = self.get_stats()
        return (f"QueuePresenter(queue={stats['queue_size']}, "
                f"undo={stats['undo_count']}, redo={stats['redo_count']})")

    # ========================================================================
    # METHOD SNAPSHOT (preserves full method during execution)
    # ========================================================================

    def snapshot_method(self):
        """Take a deep-copy snapshot of the queue before run starts."""
        self._queue_manager.snapshot_method()

    def advance_method_progress(self):
        """Increment completed-cycle counter (called after each cycle)."""
        self._queue_manager.advance_method_progress()

    def get_original_method(self) -> list:
        """Get the full original method snapshot (never mutated)."""
        return self._queue_manager.get_original_method()

    def get_method_progress(self) -> int:
        """Get number of cycles completed in the current run."""
        return self._queue_manager.get_method_progress()

    def get_remaining_from_method(self) -> list:
        """Get deep-copied remaining cycles for resume after pause."""
        return self._queue_manager.get_remaining_from_method()

    def clear_method_snapshot(self):
        """Clear the method snapshot."""
        self._queue_manager.clear_method_snapshot()

    def has_method_snapshot(self) -> bool:
        """Check whether a method snapshot exists."""
        return self._queue_manager.has_method_snapshot()
