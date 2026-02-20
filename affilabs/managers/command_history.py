"""Command History - Undo/Redo support for queue operations.

Implements the Command pattern to enable undoable queue operations.
Each operation (add, delete, reorder) is wrapped in a Command object that
knows how to execute and undo itself.

Architecture:
- Command pattern for operation encapsulation
- Undo/Redo stacks with configurable history depth
- Transaction support for batch operations
- Clear separation between UI actions and state changes
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from PySide6.QtCore import QObject, Signal

from affilabs.domain.cycle import Cycle
from affilabs.managers.queue_manager import QueueManager
from affilabs.utils.logger import logger


class Command(ABC):
    """Base class for undoable commands.

    All queue operations should be wrapped in Command objects that implement
    execute() and undo() methods. This enables automatic undo/redo support.
    """

    @abstractmethod
    def execute(self) -> bool:
        """Execute the command.

        Returns:
            True if command executed successfully
        """
        pass

    @abstractmethod
    def undo(self) -> bool:
        """Undo the command.

        Returns:
            True if command was undone successfully
        """
        pass

    @abstractmethod
    def get_description(self) -> str:
        """Get human-readable description of the command.

        Returns:
            Description string for UI display
        """
        pass


class AddCycleCommand(Command):
    """Command to add a cycle to the queue."""

    def __init__(self, queue_mgr: QueueManager, cycle: Cycle):
        """Initialize add command.

        Args:
            queue_mgr: QueueManager instance
            cycle: Cycle to add
        """
        self.queue_mgr = queue_mgr
        self.cycle = cycle
        self.index = None  # Will be set after execute

    def execute(self) -> bool:
        """Add cycle to queue."""
        success = self.queue_mgr.add_cycle(self.cycle)
        if success:
            self.index = self.queue_mgr.get_queue_size() - 1
            logger.debug(f"Execute: Added {self.cycle.name} at index {self.index}")
        return success

    def undo(self) -> bool:
        """Remove the added cycle."""
        if self.index is not None:
            deleted = self.queue_mgr.delete_cycle(self.index)
            if deleted:
                logger.debug(f"Undo: Removed {self.cycle.name} from index {self.index}")
                return True
        return False

    def get_description(self) -> str:
        """Get command description."""
        return f"Add {self.cycle.type} cycle"


class DeleteCycleCommand(Command):
    """Command to delete a cycle from the queue."""

    def __init__(self, queue_mgr: QueueManager, index: int):
        """Initialize delete command.

        Args:
            queue_mgr: QueueManager instance
            index: Index of cycle to delete
        """
        self.queue_mgr = queue_mgr
        self.index = index
        self.deleted_cycle = None  # Will be set after execute

    def execute(self) -> bool:
        """Delete cycle from queue."""
        self.deleted_cycle = self.queue_mgr.delete_cycle(self.index)
        if self.deleted_cycle:
            logger.debug(f"Execute: Deleted {self.deleted_cycle.name} from index {self.index}")
            return True
        return False

    def undo(self) -> bool:
        """Re-insert the deleted cycle."""
        if self.deleted_cycle:
            # Re-insert at same position
            self.queue_mgr._queue.insert(self.index, self.deleted_cycle)
            self.queue_mgr._renumber_cycles()
            self.queue_mgr.queue_changed.emit()
            logger.debug(f"Undo: Re-inserted {self.deleted_cycle.name} at index {self.index}")
            return True
        return False

    def get_description(self) -> str:
        """Get command description."""
        if self.deleted_cycle:
            return f"Delete {self.deleted_cycle.name}"
        return f"Delete cycle at index {self.index}"


class DeleteCyclesCommand(Command):
    """Command to delete multiple cycles at once."""

    def __init__(self, queue_mgr: QueueManager, indices: List[int]):
        """Initialize bulk delete command.

        Args:
            queue_mgr: QueueManager instance
            indices: List of indices to delete
        """
        self.queue_mgr = queue_mgr
        self.indices = sorted(indices)  # Sort for consistent behavior
        self.deleted_cycles = []  # Will be set after execute

    def execute(self) -> bool:
        """Delete multiple cycles from queue."""
        # Delete in reverse order to maintain indices
        for index in reversed(self.indices):
            cycle = self.queue_mgr.delete_cycle(index)
            if cycle:
                self.deleted_cycles.insert(0, (index, cycle))

        if self.deleted_cycles:
            logger.debug(f"Execute: Deleted {len(self.deleted_cycles)} cycles")
            return True
        return False

    def undo(self) -> bool:
        """Re-insert all deleted cycles."""
        if not self.deleted_cycles:
            return False

        # Re-insert in original order
        for index, cycle in self.deleted_cycles:
            self.queue_mgr._queue.insert(index, cycle)

        self.queue_mgr._renumber_cycles()
        self.queue_mgr.queue_changed.emit()
        logger.debug(f"Undo: Re-inserted {len(self.deleted_cycles)} cycles")
        return True

    def get_description(self) -> str:
        """Get command description."""
        return f"Delete {len(self.indices)} cycles"


class ReorderCycleCommand(Command):
    """Command to reorder a cycle in the queue."""

    def __init__(self, queue_mgr: QueueManager, from_idx: int, to_idx: int):
        """Initialize reorder command.

        Args:
            queue_mgr: QueueManager instance
            from_idx: Source index
            to_idx: Destination index
        """
        self.queue_mgr = queue_mgr
        self.from_idx = from_idx
        self.to_idx = to_idx

    def execute(self) -> bool:
        """Move cycle from one position to another."""
        success = self.queue_mgr.reorder_cycle(self.from_idx, self.to_idx)
        if success:
            logger.debug(f"Execute: Moved cycle from {self.from_idx} to {self.to_idx}")
        return success

    def undo(self) -> bool:
        """Move cycle back to original position."""
        # Reverse the operation
        success = self.queue_mgr.reorder_cycle(self.to_idx, self.from_idx)
        if success:
            logger.debug(f"Undo: Moved cycle from {self.to_idx} back to {self.from_idx}")
        return success

    def get_description(self) -> str:
        """Get command description."""
        return f"Reorder cycle from position {self.from_idx + 1} to {self.to_idx + 1}"


class ClearQueueCommand(Command):
    """Command to clear the entire queue."""

    def __init__(self, queue_mgr: QueueManager):
        """Initialize clear command.

        Args:
            queue_mgr: QueueManager instance
        """
        self.queue_mgr = queue_mgr
        self.cleared_cycles = []  # Will be set after execute

    def execute(self) -> bool:
        """Clear all cycles from queue."""
        # Save all cycles before clearing
        self.cleared_cycles = self.queue_mgr.get_queue_snapshot()
        count = self.queue_mgr.clear_queue()

        if count > 0:
            logger.debug(f"Execute: Cleared {count} cycles")
            return True
        return False

    def undo(self) -> bool:
        """Restore all cleared cycles."""
        if not self.cleared_cycles:
            return False

        # Re-add all cycles
        for cycle in self.cleared_cycles:
            self.queue_mgr._queue.append(cycle)

        self.queue_mgr._renumber_cycles()
        self.queue_mgr.queue_changed.emit()
        logger.debug(f"Undo: Restored {len(self.cleared_cycles)} cleared cycles")
        return True

    def get_description(self) -> str:
        """Get command description."""
        return f"Clear queue ({len(self.cleared_cycles)} cycles)"


class AddMethodCommand(Command):
    """Command to add multiple cycles as a batch (one undo removes entire method)."""

    def __init__(self, queue_mgr: QueueManager, cycles: List[Cycle], method_name: str = "Untitled Method"):
        """Initialize add method command.

        Args:
            queue_mgr: QueueManager instance
            cycles: List of cycles to add as a batch
            method_name: Display name for the method
        """
        self.queue_mgr = queue_mgr
        self.cycles = cycles
        self.method_name = method_name
        self.added_indices = []  # Track indices for undo

    def execute(self) -> bool:
        """Add all cycles to queue."""
        if not self.cycles:
            return False

        start_idx = self.queue_mgr.get_queue_size()
        success = True

        for cycle in self.cycles:
            if not self.queue_mgr.add_cycle(cycle):
                success = False
                break
            self.added_indices.append(self.queue_mgr.get_queue_size() - 1)

        if success:
            logger.debug(f"Execute: Added method '{self.method_name}' with {len(self.cycles)} cycles")
        return success

    def undo(self) -> bool:
        """Remove all added cycles (in reverse order to preserve indices)."""
        if not self.added_indices:
            return False

        # Delete in reverse order to preserve indices
        for idx in reversed(self.added_indices):
            if idx < self.queue_mgr.get_queue_size():
                self.queue_mgr.delete_cycle(idx)

        logger.debug(f"Undo: Removed method '{self.method_name}' ({len(self.added_indices)} cycles)")
        self.added_indices.clear()
        return True

    def get_description(self) -> str:
        """Get command description."""
        return f"Add method '{self.method_name}' ({len(self.cycles)} cycles)"


class CommandHistory(QObject):
    """Manages undo/redo stack for queue operations.

    Maintains two stacks:
    - Undo stack: Commands that have been executed
    - Redo stack: Commands that have been undone

    Signals:
        can_undo_changed: Emitted when undo availability changes
        can_redo_changed: Emitted when redo availability changes
        history_changed: Emitted when history state changes
    """

    # Signals
    can_undo_changed = Signal(bool)  # Can undo state changed
    can_redo_changed = Signal(bool)  # Can redo state changed
    history_changed = Signal()  # General history state change

    def __init__(self, max_history: int = 50):
        """Initialize command history.

        Args:
            max_history: Maximum number of commands to keep in history
        """
        super().__init__()
        self._undo_stack: List[Command] = []
        self._redo_stack: List[Command] = []
        self._max_history = max_history

        logger.debug(f"CommandHistory initialized (max={max_history})")

    def execute(self, command: Command) -> bool:
        """Execute a command and add it to history.

        Args:
            command: Command to execute

        Returns:
            True if command executed successfully
        """
        if command.execute():
            # Add to undo stack
            self._undo_stack.append(command)

            # Clear redo stack (new branch in history)
            was_redo_available = len(self._redo_stack) > 0
            self._redo_stack.clear()

            # Trim history if needed
            if len(self._undo_stack) > self._max_history:
                self._undo_stack.pop(0)

            # Emit signals
            self.can_undo_changed.emit(True)
            if was_redo_available:
                self.can_redo_changed.emit(False)
            self.history_changed.emit()

            logger.debug(f"Executed: {command.get_description()}")
            return True

        return False

    def undo(self) -> bool:
        """Undo the last command.

        Returns:
            True if undo succeeded
        """
        if not self._undo_stack:
            logger.debug("Cannot undo - history is empty")
            return False

        command = self._undo_stack.pop()

        if command.undo():
            # Move to redo stack
            self._redo_stack.append(command)

            # Emit signals
            self.can_undo_changed.emit(len(self._undo_stack) > 0)
            self.can_redo_changed.emit(True)
            self.history_changed.emit()

            logger.info(f"↩️ Undo: {command.get_description()}")
            return True
        else:
            # Undo failed, put command back
            self._undo_stack.append(command)
            logger.warning(f"Undo failed: {command.get_description()}")
            return False

    def redo(self) -> bool:
        """Redo the last undone command.

        Returns:
            True if redo succeeded
        """
        if not self._redo_stack:
            logger.debug("Cannot redo - redo stack is empty")
            return False

        command = self._redo_stack.pop()

        if command.execute():
            # Move back to undo stack
            self._undo_stack.append(command)

            # Emit signals
            self.can_undo_changed.emit(True)
            self.can_redo_changed.emit(len(self._redo_stack) > 0)
            self.history_changed.emit()

            logger.info(f"↪️ Redo: {command.get_description()}")
            return True
        else:
            # Redo failed, put command back
            self._redo_stack.append(command)
            logger.warning(f"Redo failed: {command.get_description()}")
            return False

    def can_undo(self) -> bool:
        """Check if undo is available.

        Returns:
            True if there are commands to undo
        """
        return len(self._undo_stack) > 0

    def can_redo(self) -> bool:
        """Check if redo is available.

        Returns:
            True if there are commands to redo
        """
        return len(self._redo_stack) > 0

    def get_undo_description(self) -> Optional[str]:
        """Get description of next undo action.

        Returns:
            Description string, or None if no undo available
        """
        if self._undo_stack:
            return self._undo_stack[-1].get_description()
        return None

    def get_redo_description(self) -> Optional[str]:
        """Get description of next redo action.

        Returns:
            Description string, or None if no redo available
        """
        if self._redo_stack:
            return self._redo_stack[-1].get_description()
        return None

    def clear(self):
        """Clear all history."""
        was_undo_available = len(self._undo_stack) > 0
        was_redo_available = len(self._redo_stack) > 0

        self._undo_stack.clear()
        self._redo_stack.clear()

        if was_undo_available:
            self.can_undo_changed.emit(False)
        if was_redo_available:
            self.can_redo_changed.emit(False)
        self.history_changed.emit()

        logger.debug("Command history cleared")

    def get_undo_count(self) -> int:
        """Get number of commands in undo stack.

        Returns:
            Undo stack size
        """
        return len(self._undo_stack)

    def get_redo_count(self) -> int:
        """Get number of commands in redo stack.

        Returns:
            Redo stack size
        """
        return len(self._redo_stack)

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (f"CommandHistory(undo={len(self._undo_stack)}, "
                f"redo={len(self._redo_stack)})")
