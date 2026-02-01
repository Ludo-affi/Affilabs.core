"""Test suite for CommandHistory - Undo/Redo functionality.

Tests all command types and history management:
- AddCycleCommand
- DeleteCycleCommand
- DeleteCyclesCommand (bulk)
- ReorderCycleCommand
- ClearQueueCommand
- Undo/Redo operations
- History limits
- Signal emissions
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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


def test_add_cycle_undo_redo():
    """Test adding a cycle with undo/redo."""
    print("\n=== Test 1: Add Cycle - Undo - Redo ===")

    queue_mgr = QueueManager()
    history = CommandHistory()

    # Create and add cycle
    cycle = Cycle(type="Baseline", name="Test", length_minutes=1.0)
    cmd = AddCycleCommand(queue_mgr, cycle)

    # Execute
    result = history.execute(cmd)
    assert result == True, "Add command should succeed"
    assert queue_mgr.get_queue_size() == 1, "Queue should have 1 cycle"
    assert history.can_undo() == True, "Should be able to undo"
    assert history.can_redo() == False, "Should not be able to redo yet"
    print(f"✓ Added {cycle.name}, queue size: {queue_mgr.get_queue_size()}")

    # Undo
    result = history.undo()
    assert result == True, "Undo should succeed"
    assert queue_mgr.get_queue_size() == 0, "Queue should be empty after undo"
    assert history.can_undo() == False, "Should not be able to undo anymore"
    assert history.can_redo() == True, "Should be able to redo"
    print(f"✓ Undone, queue size: {queue_mgr.get_queue_size()}")

    # Redo
    result = history.redo()
    assert result == True, "Redo should succeed"
    assert queue_mgr.get_queue_size() == 1, "Queue should have 1 cycle again"
    assert history.can_undo() == True, "Should be able to undo again"
    assert history.can_redo() == False, "Should not be able to redo anymore"
    print(f"✓ Redone, queue size: {queue_mgr.get_queue_size()}")

    print("✅ Test 1 PASSED\n")


def test_delete_cycle_undo_redo():
    """Test deleting a cycle with undo/redo."""
    print("\n=== Test 2: Delete Cycle - Undo - Redo ===")

    queue_mgr = QueueManager()
    history = CommandHistory()

    # Add cycles directly
    cycle1 = Cycle(type="Baseline", name="Cycle 1", length_minutes=1.0)
    cycle2 = Cycle(type="Association", name="Cycle 2", length_minutes=2.0)
    cycle3 = Cycle(type="Dissociation", name="Cycle 3", length_minutes=1.5)

    queue_mgr.add_cycle(cycle1)
    queue_mgr.add_cycle(cycle2)
    queue_mgr.add_cycle(cycle3)

    initial = queue_mgr.get_queue_snapshot()
    print(f"Initial queue: {[(c.name, c.cycle_id) for c in initial]}")

    # Delete middle cycle (cycle_id=2)
    cmd = DeleteCycleCommand(queue_mgr, 1)  # Delete "Cycle 2"
    result = history.execute(cmd)

    assert result == True, "Delete should succeed"
    assert queue_mgr.get_queue_size() == 2, "Should have 2 cycles left"
    remaining = queue_mgr.get_queue_snapshot()
    # After deletion, cycles are renumbered: Cycle 1 (ID 1) and Cycle 2 (ID 3)
    assert remaining[0].cycle_id == 1, "First cycle should have ID 1"
    assert remaining[1].cycle_id == 3, "Second cycle should have ID 3 (was Cycle 3)"
    assert remaining[0].name == "Cycle 1", "First cycle name is Cycle 1"
    assert remaining[1].name == "Cycle 2", "Second cycle name is now Cycle 2 (renumbered)"
    print(f"✓ Deleted cycle ID 2, remaining: {[(c.name, c.cycle_id) for c in remaining]}")

    # Undo delete
    result = history.undo()
    assert result == True, "Undo should succeed"
    assert queue_mgr.get_queue_size() == 3, "Should have 3 cycles again"
    restored = queue_mgr.get_queue_snapshot()
    # Cycles are restored and renumbered
    assert restored[0].cycle_id == 1, "First should have ID 1"
    assert restored[1].cycle_id == 2, "Second should have ID 2 (restored)"
    assert restored[2].cycle_id == 3, "Third should have ID 3"
    assert restored[1].name == "Cycle 2", "Names are renumbered sequentially"
    print(f"✓ Undone, restored: {[(c.name, c.cycle_id) for c in restored]}")

    # Redo delete
    result = history.redo()
    assert result == True, "Redo should succeed"
    assert queue_mgr.get_queue_size() == 2, "Should have 2 cycles again"
    final = queue_mgr.get_queue_snapshot()
    assert final[0].cycle_id == 1, "First should have ID 1"
    assert final[1].cycle_id == 3, "Second should have ID 3 (was third cycle)"
    print(f"✓ Redone, final: {[(c.name, c.cycle_id) for c in final]}")

    print("✅ Test 2 PASSED\n")


def test_bulk_delete_undo():
    """Test bulk delete with undo."""
    print("\n=== Test 3: Bulk Delete - Undo ===")

    queue_mgr = QueueManager()
    history = CommandHistory()

    # Add 5 cycles
    for i in range(1, 6):
        cycle = Cycle(type="Baseline", name=f"Cycle {i}", length_minutes=1.0)
        queue_mgr.add_cycle(cycle)

    print(f"Initial queue (5 cycles): {[(c.name, c.cycle_id) for c in queue_mgr.get_queue_snapshot()]}")

    # Delete cycles at indices 1, 2, 4 (not contiguous)
    cmd = DeleteCyclesCommand(queue_mgr, [1, 2, 4])
    result = history.execute(cmd)

    assert result == True, "Bulk delete should succeed"
    assert queue_mgr.get_queue_size() == 2, "Should have 2 cycles left"
    remaining = queue_mgr.get_queue_snapshot()
    assert remaining[0].cycle_id == 1, "First should have ID 1"
    assert remaining[1].cycle_id == 4, "Second should have ID 4 (was 4th cycle)"
    assert remaining[0].name == "Cycle 1", "Names renumbered"
    assert remaining[1].name == "Cycle 2", "Names renumbered"
    print(f"✓ Deleted 3 cycles, remaining: {[(c.name, c.cycle_id) for c in remaining]}")

    # Undo bulk delete
    result = history.undo()
    assert result == True, "Undo should succeed"
    assert queue_mgr.get_queue_size() == 5, "Should have all 5 cycles back"
    restored = queue_mgr.get_queue_snapshot()
    for i in range(5):
        assert restored[i].cycle_id == i+1, f"Position {i} should have ID {i+1}"
        assert restored[i].name == f"Cycle {i+1}", f"Names should be renumbered"
    print(f"✓ Undone, all cycles restored: {[(c.name, c.cycle_id) for c in restored]}")

    print("✅ Test 3 PASSED\n")


def test_reorder_cycle_undo_redo():
    """Test reordering with undo/redo."""
    print("\n=== Test 4: Reorder Cycle - Undo - Redo ===")

    queue_mgr = QueueManager()
    history = CommandHistory()

    # Add 4 cycles
    for i in range(1, 5):
        cycle = Cycle(type="Baseline", name=f"Cycle {i}", length_minutes=1.0)
        queue_mgr.add_cycle(cycle)

    print(f"Initial order: {[(c.name, c.cycle_id) for c in queue_mgr.get_queue_snapshot()]}")

    # Move Cycle 1 (index 0) to position 2 (index 2)
    # Expected IDs: [2, 3, 1, 4] after reorder and renumber
    cmd = ReorderCycleCommand(queue_mgr, 0, 2)
    result = history.execute(cmd)

    assert result == True, "Reorder should succeed"
    reordered = queue_mgr.get_queue_snapshot()
    assert reordered[0].cycle_id == 2, "Position 0 should have ID 2"
    assert reordered[1].cycle_id == 3, "Position 1 should have ID 3"
    assert reordered[2].cycle_id == 1, "Position 2 should have ID 1 (moved)"
    assert reordered[3].cycle_id == 4, "Position 3 should have ID 4"
    # Names are always renumbered to match position
    assert reordered[0].name == "Cycle 1", "Names renumbered"
    assert reordered[2].name == "Cycle 3", "Names renumbered"
    print(f"✓ Reordered: {[(c.name, c.cycle_id) for c in reordered]}")

    # Undo reorder
    result = history.undo()
    assert result == True, "Undo should succeed"
    restored = queue_mgr.get_queue_snapshot()
    for i in range(4):
        assert restored[i].cycle_id == i+1, f"Position {i} should have ID {i+1}"
        assert restored[i].name == f"Cycle {i+1}", f"Names should be renumbered"
    print(f"✓ Undone: {[(c.name, c.cycle_id) for c in restored]}")

    # Redo reorder
    result = history.redo()
    assert result == True, "Redo should succeed"
    final = queue_mgr.get_queue_snapshot()
    assert final[0].cycle_id == 2, "Position 0 should have ID 2 again"
    assert final[2].cycle_id == 1, "Position 2 should have ID 1 again (moved)"
    print(f"✓ Redone: {[(c.name, c.cycle_id) for c in final]}")

    print("✅ Test 4 PASSED\n")


def test_clear_queue_undo():
    """Test clearing queue with undo."""
    print("\n=== Test 5: Clear Queue - Undo ===")

    queue_mgr = QueueManager()
    history = CommandHistory()
    initial_ids = []  # Declare at function scope

    # Add 3 cycles with custom names
    cycles_data = [
        ("Baseline", 1.0),
        ("Association", 2.0),
        ("Dissociation", 1.5)
    ]

    for i, (type_, length_minutes) in enumerate(cycles_data):
        cycle = Cycle(type=type_, length_minutes=length_minutes)
        queue_mgr.add_cycle(cycle)

    initial_ids = [c.cycle_id for c in queue_mgr.get_queue_snapshot()]
    print(f"Initial queue: {[(c.name, c.cycle_id) for c in queue_mgr.get_queue_snapshot()]}")

    # Clear queue
    cmd = ClearQueueCommand(queue_mgr)
    result = history.execute(cmd)

    assert result == True, "Clear should succeed"
    assert queue_mgr.get_queue_size() == 0, "Queue should be empty"
    print(f"✓ Cleared queue, size: {queue_mgr.get_queue_size()}")

    # Undo clear
    result = history.undo()
    assert result == True, "Undo should succeed"
    assert queue_mgr.get_queue_size() == 3, "Should have 3 cycles back"
    restored = queue_mgr.get_queue_snapshot()
    # Check IDs were preserved
    for i, expected_id in enumerate(initial_ids):
        assert restored[i].cycle_id == expected_id, f"Position {i} should have ID {expected_id}"
        assert restored[i].name == f"Cycle {i+1}", f"Names should be renumbered"
    print(f"✓ Undone, restored: {[(c.name, c.cycle_id) for c in restored]}")

    print("✅ Test 5 PASSED\n")


def test_history_limit():
    """Test that history respects max_history limit."""
    print("\n=== Test 6: History Limit (max=5) ===")

    queue_mgr = QueueManager()
    history = CommandHistory(max_history=5)

    # Execute 10 add commands
    for i in range(10):
        cycle = Cycle(type="Baseline", name=f"Cycle {i+1}", length_minutes=1.0)
        cmd = AddCycleCommand(queue_mgr, cycle)
        history.execute(cmd)

    print(f"Executed 10 commands, undo stack size: {history.get_undo_count()}")
    assert history.get_undo_count() == 5, "Should only keep last 5 commands"

    # Undo 5 times
    for i in range(5):
        result = history.undo()
        assert result == True, f"Undo {i+1} should succeed"

    print(f"✓ Undone 5 times, queue size: {queue_mgr.get_queue_size()}")
    assert queue_mgr.get_queue_size() == 5, "Should have 5 cycles left (oldest not undoable)"
    assert history.can_undo() == False, "Should not be able to undo anymore"

    print("✅ Test 6 PASSED\n")


def test_new_command_clears_redo():
    """Test that executing new command clears redo stack."""
    print("\n=== Test 7: New Command Clears Redo ===")

    queue_mgr = QueueManager()
    history = CommandHistory()

    # Add 3 cycles
    for i in range(1, 4):
        cycle = Cycle(type="Baseline", name=f"Cycle {i}", length_minutes=1.0)
        cmd = AddCycleCommand(queue_mgr, cycle)
        history.execute(cmd)

    # Undo twice
    history.undo()
    history.undo()

    print(f"After 2 undos: undo_count={history.get_undo_count()}, redo_count={history.get_redo_count()}")
    assert history.get_redo_count() == 2, "Should have 2 in redo stack"
    assert history.can_redo() == True, "Should be able to redo"

    # Execute new command
    new_cycle = Cycle(type="Association", name="New Cycle", length_minutes=2.0)
    cmd = AddCycleCommand(queue_mgr, new_cycle)
    history.execute(cmd)

    print(f"After new command: undo_count={history.get_undo_count()}, redo_count={history.get_redo_count()}")
    assert history.get_redo_count() == 0, "Redo stack should be cleared"
    assert history.can_redo() == False, "Should not be able to redo"

    print("✅ Test 7 PASSED\n")


def test_signal_emissions():
    """Test that history emits signals correctly."""
    print("\n=== Test 8: Signal Emissions ===")

    queue_mgr = QueueManager()
    history = CommandHistory()

    # Track signals
    signals_received = {
        'can_undo_changed': [],
        'can_redo_changed': [],
        'history_changed': 0
    }

    def on_can_undo_changed(value):
        signals_received['can_undo_changed'].append(value)

    def on_can_redo_changed(value):
        signals_received['can_redo_changed'].append(value)

    def on_history_changed():
        signals_received['history_changed'] += 1

    # Connect signals
    history.can_undo_changed.connect(on_can_undo_changed)
    history.can_redo_changed.connect(on_can_redo_changed)
    history.history_changed.connect(on_history_changed)

    # Execute command
    cycle = Cycle(type="Baseline", name="Test", length_minutes=1.0)
    cmd = AddCycleCommand(queue_mgr, cycle)
    history.execute(cmd)

    print(f"After execute: can_undo={signals_received['can_undo_changed']}, "
          f"can_redo={signals_received['can_redo_changed']}, "
          f"history_changed={signals_received['history_changed']}")

    assert True in signals_received['can_undo_changed'], "Should emit can_undo=True"
    assert signals_received['history_changed'] >= 1, "Should emit history_changed"

    # Undo
    history.undo()

    print(f"After undo: can_undo={signals_received['can_undo_changed']}, "
          f"can_redo={signals_received['can_redo_changed']}, "
          f"history_changed={signals_received['history_changed']}")

    assert False in signals_received['can_undo_changed'], "Should emit can_undo=False"
    assert True in signals_received['can_redo_changed'], "Should emit can_redo=True"

    print("✅ Test 8 PASSED\n")


def test_command_descriptions():
    """Test command description strings."""
    print("\n=== Test 9: Command Descriptions ===")

    queue_mgr = QueueManager()
    history = CommandHistory()

    # Add cycle
    cycle = Cycle(type="Baseline", name="Test Lin", length_minutes=1.0)
    cmd1 = AddCycleCommand(queue_mgr, cycle)
    history.execute(cmd1)

    desc = history.get_undo_description()
    print(f"Add command description: '{desc}'")
    assert "Add" in desc, "Should mention 'Add'"
    assert "Baseline" in desc, "Should mention cycle type"

    # Delete cycle
    cmd2 = DeleteCycleCommand(queue_mgr, 0)
    history.execute(cmd2)

    desc = history.get_undo_description()
    print(f"Delete command description: '{desc}'")
    assert "Delete" in desc, "Should mention 'Delete'"

    # Undo delete
    history.undo()

    desc = history.get_redo_description()
    print(f"Redo description: '{desc}'")
    assert desc is not None, "Should have redo description"

    # Clear history
    history.clear()

    assert history.get_undo_description() is None, "Should have no undo description"
    assert history.get_redo_description() is None, "Should have no redo description"
    print("✓ Descriptions correct, clear() works")

    print("✅ Test 9 PASSED\n")


def run_all_tests():
    """Run all command history tests."""
    print("="*70)
    print("COMMAND HISTORY TEST SUITE")
    print("="*70)

    tests = [
        test_add_cycle_undo_redo,
        test_delete_cycle_undo_redo,
        test_bulk_delete_undo,
        test_reorder_cycle_undo_redo,
        test_clear_queue_undo,
        test_history_limit,
        test_new_command_clears_redo,
        test_signal_emissions,
        test_command_descriptions
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"❌ {test.__name__} FAILED: {e}\n")
            failed += 1
        except Exception as e:
            print(f"💥 {test.__name__} ERROR: {e}\n")
            failed += 1

    print("="*70)
    print(f"TEST RESULTS: {passed} passed, {failed} failed")
    print("="*70)

    if failed == 0:
        print("\n🎉 ALL TESTS PASSED! CommandHistory is ready for integration.")
        print("\nNext steps:")
        print("  1. Integrate CommandHistory with Application class")
        print("  2. Add Undo/Redo toolbar buttons")
        print("  3. Wire up Ctrl+Z / Ctrl+Shift+Z shortcuts")
        print("  4. Proceed to Phase 3: QueuePresenter")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
