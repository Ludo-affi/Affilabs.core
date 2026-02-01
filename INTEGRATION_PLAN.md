"""Integration Plan: QueuePresenter → Application

This document outlines how to integrate the new queue architecture into main.py's Application class.

CURRENT STATE (Old Architecture):
================================
- Queue stored in: self.segment_queue (List[Cycle])
- Queue operations: Direct list manipulation (append, pop, etc.)
- UI table: self.ui.sidebar.summary_table (QTableWidget)
- Backup: _save_queue_backup(), _load_queue_backup()
- Operations: _on_add_to_queue(), _delete_cycle_from_queue(), etc.

NEW ARCHITECTURE (To Integrate):
================================
1. QueueManager - State management (managers/queue_manager.py)
2. CommandHistory - Undo/redo (managers/command_history.py)
3. QueuePresenter - Coordination (presenters/queue_presenter.py)
4. QueueSummaryWidget - Table (widgets/queue_summary_widget.py)
5. QueueToolbar - Actions (widgets/queue_toolbar.py)

INTEGRATION STEPS:
==================

Step 1: Initialize New Components
----------------------------------
Location: Application.__init__() ~line 779

BEFORE:
    self.segment_queue = []  # List of segment definition dicts

AFTER:
    # Initialize new queue architecture
    from affilabs.presenters.queue_presenter import QueuePresenter
    self.queue_presenter = QueuePresenter(max_history=50)

    # Backward compatibility: segment_queue property delegates to presenter
    @property
    def segment_queue(self):
        return self.queue_presenter.get_queue_snapshot()

Step 2: Replace Queue Table Widget
-----------------------------------
Location: UI setup where summary_table is created

BEFORE:
    self.ui.sidebar.summary_table (created in affilabs_core_ui.py)

AFTER:
    from affilabs.widgets.queue_summary_widget import QueueSummaryWidget
    self.queue_table = QueueSummaryWidget()
    self.queue_table.set_presenter(self.queue_presenter)

    # Connect signals
    self.queue_table.cycle_reordered.connect(self.queue_presenter.reorder_cycle)
    self.queue_table.cycles_deleted.connect(self.queue_presenter.delete_cycles)

Step 3: Add Queue Toolbar
--------------------------
Location: Sidebar UI layout

NEW:
    from affilabs.widgets.queue_toolbar import QueueToolbar
    self.queue_toolbar = QueueToolbar(self.window)

    # Connect toolbar to presenter
    self.queue_toolbar.undo_requested.connect(self.queue_presenter.undo)
    self.queue_toolbar.redo_requested.connect(self.queue_presenter.redo)
    self.queue_toolbar.delete_selected_requested.connect(
        lambda: self.queue_presenter.delete_cycles(self.queue_table.get_selected_indices())
    )
    self.queue_toolbar.clear_all_requested.connect(self.queue_presenter.clear_queue)

    # Connect presenter to toolbar
    self.queue_presenter.can_undo_changed.connect(self.queue_toolbar.set_undo_enabled)
    self.queue_presenter.can_redo_changed.connect(self.queue_toolbar.set_redo_enabled)
    self.queue_presenter.undo_description_changed.connect(self.queue_toolbar.set_undo_tooltip)

Step 4: Replace Queue Operations
---------------------------------

OLD METHOD: _on_add_to_queue()
REPLACE WITH:
    def _on_add_to_queue(self):
        # ... validation code ...
        cycle = Cycle(type=cycle_type, length_minutes=length_minutes, note=note)
        self.queue_presenter.add_cycle(cycle)
        # ... UI updates now handled by signals ...

OLD METHOD: _delete_cycle_from_queue(row)
REPLACE WITH:
    def _delete_cycle_from_queue(self, row):
        self.queue_presenter.delete_cycle(row)
        # UI update handled by signal

OLD METHOD: _get_next_cycle()
REPLACE WITH:
    def _get_next_cycle(self):
        if not self.queue_presenter.get_queue_size():
            return None

        self.queue_presenter.lock_queue()
        cycle = self.queue_presenter.pop_next_cycle()
        # ... rest of method ...

OLD METHOD: _on_cycle_completed()
REPLACE WITH:
    def _on_cycle_completed(self, completed_cycle):
        self.queue_presenter.mark_cycle_completed(completed_cycle)
        self.queue_presenter.unlock_queue()
        # ... rest of method ...

Step 5: Replace Backup/Restore
-------------------------------

OLD METHOD: _save_queue_backup()
REPLACE WITH:
    def _save_queue_backup(self):
        state = self.queue_presenter.get_state()
        # ... save state dict to file ...

OLD METHOD: _load_queue_backup()
REPLACE WITH:
    def _load_queue_backup(self):
        # ... load state dict from file ...
        self.queue_presenter.restore_state(state)

Step 6: Update UI Refresh Methods
----------------------------------

OLD METHOD: _update_summary_table()
REMOVE - Handled by QueueSummaryWidget auto-refresh

OLD METHOD: _renumber_cycles()
REMOVE - Handled by QueueManager automatically

Step 7: Backward Compatibility
-------------------------------
Keep these methods/properties for existing code:

@property
def segment_queue(self) -> List[Cycle]:
    \"\"\"Backward compatibility: Returns queue snapshot.\"\"\"
    return self.queue_presenter.get_queue_snapshot()

@segment_queue.setter
def segment_queue(self, value: List[Cycle]):
    \"\"\"Backward compatibility: Clear and restore queue.\"\"\"
    self.queue_presenter.clear_queue()
    for cycle in value:
        self.queue_presenter.add_cycle(cycle)

METHODS TO REMOVE/DEPRECATE:
=============================
- _update_summary_table() - Replaced by widget auto-refresh
- _renumber_cycles() - Handled by QueueManager
- _validate_segment_queue() - Can keep for extra validation
- _delete_cycle_from_queue() - Simplified to delegate to presenter
- Most table manipulation code - Handled by QueueSummaryWidget

TESTING CHECKLIST:
==================
[ ] Add cycle → appears in table
[ ] Delete cycle → removed from table
[ ] Ctrl+Z → undoes last operation
[ ] Ctrl+Shift+Z → redoes operation
[ ] Start run → queue locks (grays out)
[ ] Complete cycle → queue unlocks
[ ] Drag-drop reorder → cycles reordered
[ ] Multi-select delete → multiple cycles removed
[ ] Save/Load backup → queue restored
[ ] Crash recovery → queue restored on restart

BENEFITS OF MIGRATION:
======================
✓ Undo/Redo support (50 operations)
✓ Drag-and-drop reordering
✓ Bulk operations (multi-delete)
✓ Keyboard shortcuts (Ctrl+Z, Ctrl+Shift+Z)
✓ Clean separation of concerns
✓ Fully tested components (40+ tests passing)
✓ Easy to extend with new features
✓ Thread-safe queue locking

MIGRATION STRATEGY:
===================
1. Gradual replacement (not all at once)
2. Keep old code initially (comment out, don't delete)
3. Test each step before proceeding
4. Maintain backward compatibility during transition
5. Remove old code only after full verification
"""