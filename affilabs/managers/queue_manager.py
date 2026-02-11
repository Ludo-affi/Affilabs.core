"""Queue Manager - Centralized queue state and operations.

This module provides a clean separation of queue state management from UI concerns.
All queue operations (add, delete, reorder) go through this manager, which emits
signals to notify listeners of changes.

Architecture:
- Single source of truth for queue state
- Signal-based notifications for UI updates
- Lock mechanism to prevent race conditions
- Immutable snapshots for safe access
- ID management and cycle renumbering
"""

from typing import List, Optional
from PySide6.QtCore import QObject, Signal

from affilabs.domain.cycle import Cycle
from affilabs.utils.logger import logger


class QueueManager(QObject):
    """Centralized queue state and operations manager.

    Manages the cycle queue with support for:
    - Adding/deleting/reordering cycles
    - Queue locking during execution
    - Automatic ID assignment
    - Sequential name renumbering
    - Completed cycle tracking
    - Signal-based notifications

    Signals:
        queue_changed: Emitted when queue state changes
        cycle_added: Emitted when a cycle is added (cycle)
        cycle_deleted: Emitted when a cycle is deleted (index, cycle)
        cycle_reordered: Emitted when a cycle is moved (from_idx, to_idx)
        queue_locked: Emitted when queue is locked
        queue_unlocked: Emitted when queue is unlocked
    """

    # Signals for state changes
    queue_changed = Signal()  # General queue state change
    cycle_added = Signal(Cycle)  # New cycle added
    cycle_deleted = Signal(int, Cycle)  # Cycle deleted (index, cycle)
    cycle_reordered = Signal(int, int)  # Cycle moved (from_idx, to_idx)
    queue_locked = Signal()  # Queue locked for execution
    queue_unlocked = Signal()  # Queue unlocked

    def __init__(self):
        """Initialize queue manager with empty state."""
        super().__init__()
        self._queue: List[Cycle] = []
        self._completed: List[Cycle] = []
        self._cycle_counter = 0
        self._lock = False

        logger.debug("QueueManager initialized")

    # ==================== QUEUE OPERATIONS ====================

    def add_cycle(self, cycle: Cycle) -> bool:
        """Add a cycle to the end of the queue.

        NOTE: Adding cycles is ALLOWED even when queue is locked during execution.
        This enables appending additional cycles to the back of a running queue.
        Only deletion and reordering are blocked when locked.

        Args:
            cycle: Cycle object to add (will be assigned a unique ID)

        Returns:
            True if cycle was added, False on error
        """
        # REMOVED: lock check - allow adding cycles during execution
        # Users should be able to append new cycles to a running method

        # Assign permanent unique ID
        self._cycle_counter += 1
        cycle.cycle_id = self._cycle_counter

        # Add to queue
        self._queue.append(cycle)

        # Renumber for sequential display
        self._renumber_cycles()

        # Notify listeners
        self.cycle_added.emit(cycle)
        self.queue_changed.emit()

        logger.info(f"✅ Added cycle to queue: {cycle.name} (ID: {cycle.cycle_id})")
        return True

    def delete_cycle(self, index: int) -> Optional[Cycle]:
        """Delete a cycle at the specified index.

        Args:
            index: Position in queue (0-based)

        Returns:
            The deleted Cycle object, or None if operation failed
        """
        if self._lock:
            logger.warning("Cannot delete cycle - queue is locked")
            return None

        if index < 0 or index >= len(self._queue):
            logger.warning(f"Invalid index {index} for queue size {len(self._queue)}")
            return None

        # Remove from queue
        cycle = self._queue.pop(index)

        # Renumber remaining cycles
        self._renumber_cycles()

        # Notify listeners
        self.cycle_deleted.emit(index, cycle)
        self.queue_changed.emit()

        logger.info(f"🗑️ Deleted cycle: {cycle.name} (ID: {cycle.cycle_id})")
        return cycle

    def delete_cycles(self, indices: List[int]) -> List[Cycle]:
        """Delete multiple cycles at once.

        Args:
            indices: List of positions to delete (will be sorted in reverse)

        Returns:
            List of deleted Cycle objects
        """
        if self._lock:
            logger.warning("Cannot delete cycles - queue is locked")
            return []

        deleted = []

        # Sort indices in reverse order to maintain validity during deletion
        for index in sorted(indices, reverse=True):
            if 0 <= index < len(self._queue):
                cycle = self._queue.pop(index)
                deleted.append(cycle)
                self.cycle_deleted.emit(index, cycle)

        # Renumber once after all deletions
        self._renumber_cycles()
        self.queue_changed.emit()

        logger.info(f"🗑️ Deleted {len(deleted)} cycles")
        return deleted

    def reorder_cycle(self, from_idx: int, to_idx: int) -> bool:
        """Move a cycle from one position to another.

        Args:
            from_idx: Source position
            to_idx: Destination position

        Returns:
            True if cycle was moved, False if operation failed
        """
        if self._lock:
            logger.warning("Cannot reorder cycle - queue is locked")
            return False

        if from_idx < 0 or from_idx >= len(self._queue):
            logger.warning(f"Invalid source index {from_idx}")
            return False

        if to_idx < 0 or to_idx >= len(self._queue):
            logger.warning(f"Invalid destination index {to_idx}")
            return False

        if from_idx == to_idx:
            return True  # No-op

        # Move cycle
        cycle = self._queue.pop(from_idx)
        self._queue.insert(to_idx, cycle)

        # Renumber for sequential display
        self._renumber_cycles()

        # Notify listeners
        self.cycle_reordered.emit(from_idx, to_idx)
        self.queue_changed.emit()

        logger.info(f"🔄 Moved cycle from position {from_idx} to {to_idx}")
        return True

    def clear_queue(self) -> int:
        """Remove all cycles from the queue.

        Returns:
            Number of cycles that were cleared
        """
        if self._lock:
            logger.warning("Cannot clear queue - queue is locked")
            return 0

        count = len(self._queue)
        self._queue.clear()
        self.queue_changed.emit()

        logger.info(f"🧹 Cleared {count} cycles from queue")
        return count

    def pop_next_cycle(self) -> Optional[Cycle]:
        """Remove and return the first cycle in the queue (FIFO).

        NOTE: Does NOT renumber remaining cycles - they keep their original cycle_num.
        This allows the queue table to show absolute cycle numbers (e.g. #2, #3, #4 after #1 starts)
        rather than re-indexing to #1, #2, #3 every time a cycle is popped.

        Returns:
            The next Cycle to execute, or None if queue is empty
        """
        if not self._queue:
            logger.warning("Cannot pop - queue is empty")
            return None

        cycle = self._queue.pop(0)
        # Deliberately NOT calling _renumber_cycles() here - preserve original cycle numbers
        self.queue_changed.emit()

        logger.info(f"⏭ Popped next cycle: {cycle.name} (ID: {cycle.cycle_id})")
        logger.debug(f"   {len(self._queue)} cycles remaining in queue (NOT renumbered)")
        return cycle

    # ==================== COMPLETED CYCLES ====================

    def mark_completed(self, cycle: Cycle):
        """Mark a cycle as completed and add to history.

        Args:
            cycle: Completed Cycle object
        """
        self._completed.append(cycle)
        logger.info(f"✅ Marked cycle as completed: {cycle.name} (ID: {cycle.cycle_id})")

    def get_completed_cycles(self) -> List[Cycle]:
        """Get list of all completed cycles.

        Returns:
            Copy of completed cycles list
        """
        return self._completed.copy()

    def clear_completed(self) -> int:
        """Clear completed cycles history.

        Returns:
            Number of completed cycles that were cleared
        """
        count = len(self._completed)
        self._completed.clear()
        logger.info(f"🧹 Cleared {count} completed cycles")
        return count

    # ==================== QUEUE ACCESS ====================

    def get_queue_snapshot(self) -> List[Cycle]:
        """Get immutable snapshot of current queue state.

        Returns:
            Copy of queue list (safe to iterate without locks)
        """
        return self._queue.copy()

    def get_cycle_at(self, index: int) -> Optional[Cycle]:
        """Get cycle at specific index without removing it.

        Args:
            index: Position in queue

        Returns:
            Cycle at index, or None if index invalid
        """
        if 0 <= index < len(self._queue):
            return self._queue[index]
        return None

    def peek_next_cycle(self) -> Optional[Cycle]:
        """Get the next cycle without removing it.

        Returns:
            Next Cycle to execute, or None if queue is empty
        """
        if self._queue:
            return self._queue[0]
        return None

    def get_queue_size(self) -> int:
        """Get current number of cycles in queue.

        Returns:
            Queue length
        """
        return len(self._queue)

    def get_completed_count(self) -> int:
        """Get number of completed cycles.

        Returns:
            Completed cycles count
        """
        return len(self._completed)

    def is_empty(self) -> bool:
        """Check if queue is empty.

        Returns:
            True if no cycles in queue
        """
        return len(self._queue) == 0

    # ==================== QUEUE LOCKING ====================

    def lock(self):
        """Lock queue to prevent modifications during cycle execution."""
        if not self._lock:
            self._lock = True
            self.queue_locked.emit()
            logger.debug("🔒 Queue locked")

    def unlock(self):
        """Unlock queue after cycle execution completes."""
        if self._lock:
            self._lock = False
            self.queue_unlocked.emit()
            logger.debug("🔓 Queue unlocked")

    def is_locked(self) -> bool:
        """Check if queue is currently locked.

        Returns:
            True if queue is locked
        """
        return self._lock

    # ==================== INTERNAL HELPERS ====================

    def _renumber_cycles(self):
        """Renumber all cycles to maintain sequential display names.

        Updates cycle.name to "Cycle 1", "Cycle 2", etc. based on
        current position in queue. Does NOT change cycle.cycle_id
        (permanent tracking ID).
        """
        for i, cycle in enumerate(self._queue):
            cycle.name = f"Cycle {i + 1}"
            if hasattr(cycle, "cycle_num"):
                cycle.cycle_num = i + 1

        if len(self._queue) > 0:
            logger.debug(f"🔢 Renumbered {len(self._queue)} cycles (1-{len(self._queue)})")

    def _next_id(self) -> int:
        """Get next available cycle ID.

        Returns:
            Next unique cycle ID
        """
        self._cycle_counter += 1
        return self._cycle_counter

    # ==================== STATE PERSISTENCE ====================

    def get_state(self) -> dict:
        """Get complete queue state for backup/restore.

        Returns:
            Dictionary with queue, completed cycles, and counter
        """
        return {
            "queue": [c.to_dict() for c in self._queue],
            "completed": [c.to_dict() for c in self._completed],
            "cycle_counter": self._cycle_counter,
        }

    def restore_state(self, state: dict) -> bool:
        """Restore queue state from backup.

        Args:
            state: Dictionary from get_state()

        Returns:
            True if restored successfully
        """
        try:
            # Restore queue
            self._queue = [Cycle.from_dict(c) for c in state.get("queue", [])]
            self._completed = [Cycle.from_dict(c) for c in state.get("completed", [])]

            # Restore counter with safety check to prevent duplicate IDs
            stored_counter = state.get("cycle_counter", 0)
            all_cycle_ids = [
                c.cycle_id
                for c in self._queue + self._completed
                if hasattr(c, "cycle_id") and c.cycle_id
            ]
            max_existing_id = max(all_cycle_ids) if all_cycle_ids else 0
            self._cycle_counter = max(stored_counter, max_existing_id)

            self.queue_changed.emit()

            logger.info(
                f"♻️ Restored queue state: {len(self._queue)} queued, "
                f"{len(self._completed)} completed, counter={self._cycle_counter}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to restore state: {e}")
            return False

    # ==================== UTILITY METHODS ====================

    def get_total_duration(self) -> float:
        """Calculate total duration of all queued cycles.

        Returns:
            Total duration in minutes
        """
        return sum(c.length_minutes for c in self._queue)

    def find_cycle_by_id(self, cycle_id: int) -> Optional[Cycle]:
        """Find a cycle by its permanent ID.

        Args:
            cycle_id: Permanent cycle ID to search for

        Returns:
            Cycle with matching ID, or None if not found
        """
        for cycle in self._queue:
            if hasattr(cycle, "cycle_id") and cycle.cycle_id == cycle_id:
                return cycle

        for cycle in self._completed:
            if hasattr(cycle, "cycle_id") and cycle.cycle_id == cycle_id:
                return cycle

        return None

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"QueueManager(queued={len(self._queue)}, "
            f"completed={len(self._completed)}, "
            f"locked={self._lock})"
        )
