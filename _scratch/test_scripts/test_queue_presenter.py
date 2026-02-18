"""Test suite for QueuePresenter - Coordination layer testing.

Tests presenter coordination between QueueManager, CommandHistory, and UI:
- Queue operations through presenter
- Undo/redo integration
- Signal forwarding
- State management
- Execution control
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from affilabs.domain.cycle import Cycle
# Import directly to avoid other presenter dependencies
from affilabs.presenters.queue_presenter import QueuePresenter


def test_add_and_undo():
    """Test adding cycle through presenter with undo."""
    print("\n=== Test 1: Add Cycle via Presenter - Undo ===")

    presenter = QueuePresenter()

    # Add cycle
    cycle = Cycle(type="Baseline", name="Test", length_minutes=1.0)
    result = presenter.add_cycle(cycle)

    assert result == True, "Add should succeed"
    assert presenter.get_queue_size() == 1, "Queue should have 1 cycle"
    assert presenter.can_undo() == True, "Should be able to undo"
    print(f"✓ Added cycle, queue size: {presenter.get_queue_size()}")

    # Undo
    result = presenter.undo()
    assert result == True, "Undo should succeed"
    assert presenter.get_queue_size() == 0, "Queue should be empty"
    assert presenter.can_redo() == True, "Should be able to redo"
    print(f"✓ Undone, queue size: {presenter.get_queue_size()}")

    print("✅ Test 1 PASSED\n")


def test_signal_forwarding():
    """Test that presenter forwards signals from QueueManager and History."""
    print("\n=== Test 2: Signal Forwarding ===")

    presenter = QueuePresenter()

    # Track signals
    signals_received = {
        'queue_changed': 0,
        'cycle_added': 0,
        'can_undo_changed': [],
        'can_redo_changed': []
    }

    def on_queue_changed():
        signals_received['queue_changed'] += 1

    def on_cycle_added(cycle):
        signals_received['cycle_added'] += 1

    def on_can_undo(value):
        signals_received['can_undo_changed'].append(value)

    def on_can_redo(value):
        signals_received['can_redo_changed'].append(value)

    # Connect signals
    presenter.queue_changed.connect(on_queue_changed)
    presenter.cycle_added.connect(on_cycle_added)
    presenter.can_undo_changed.connect(on_can_undo)
    presenter.can_redo_changed.connect(on_can_redo)

    # Add cycle
    cycle = Cycle(type="Baseline", length_minutes=1.0)
    presenter.add_cycle(cycle)

    assert signals_received['queue_changed'] >= 1, "queue_changed should emit"
    assert signals_received['cycle_added'] == 1, "cycle_added should emit once"
    assert True in signals_received['can_undo_changed'], "can_undo should become True"
    print(f"✓ Signals forwarded: {signals_received}")

    print("✅ Test 2 PASSED\n")


def test_bulk_operations():
    """Test bulk delete through presenter."""
    print("\n=== Test 3: Bulk Delete via Presenter ===")

    presenter = QueuePresenter()

    # Add 5 cycles
    for i in range(5):
        cycle = Cycle(type="Baseline", length_minutes=1.0)
        presenter.add_cycle(cycle)

    print(f"Added 5 cycles, queue size: {presenter.get_queue_size()}")

    # Bulk delete indices 1, 2, 4
    result = presenter.delete_cycles([1, 2, 4])

    assert result == True, "Bulk delete should succeed"
    assert presenter.get_queue_size() == 2, "Should have 2 cycles left"
    print(f"✓ Deleted 3 cycles, remaining: {presenter.get_queue_size()}")

    # Undo bulk delete
    result = presenter.undo()
    assert result == True, "Undo should succeed"
    assert presenter.get_queue_size() == 5, "Should have 5 cycles back"
    print(f"✓ Undone, restored: {presenter.get_queue_size()} cycles")

    print("✅ Test 3 PASSED\n")


def test_reorder_with_undo():
    """Test reordering through presenter."""
    print("\n=== Test 4: Reorder via Presenter - Undo ===")

    presenter = QueuePresenter()

    # Add 3 cycles
    for i in range(3):
        cycle = Cycle(type="Baseline", length_minutes=1.0)
        presenter.add_cycle(cycle)

    initial = presenter.get_queue_snapshot()
    initial_ids = [c.cycle_id for c in initial]
    print(f"Initial IDs: {initial_ids}")

    # Reorder: move index 0 to index 2
    result = presenter.reorder_cycle(0, 2)

    assert result == True, "Reorder should succeed"
    reordered = presenter.get_queue_snapshot()
    reordered_ids = [c.cycle_id for c in reordered]
    assert reordered_ids != initial_ids, "Order should have changed"
    print(f"✓ Reordered IDs: {reordered_ids}")

    # Undo reorder
    result = presenter.undo()
    assert result == True, "Undo should succeed"
    restored = presenter.get_queue_snapshot()
    restored_ids = [c.cycle_id for c in restored]
    assert restored_ids == initial_ids, "Should restore original order"
    print(f"✓ Undone, restored IDs: {restored_ids}")

    print("✅ Test 4 PASSED\n")


def test_queue_locking():
    """Test queue lock/unlock through presenter."""
    print("\n=== Test 5: Queue Locking ===")

    presenter = QueuePresenter()

    # Add cycle
    cycle = Cycle(type="Baseline", length_minutes=1.0)
    presenter.add_cycle(cycle)

    assert presenter.is_queue_locked() == False, "Queue should start unlocked"
    print("✓ Queue initially unlocked")

    # Lock queue
    presenter.lock_queue()
    assert presenter.is_queue_locked() == True, "Queue should be locked"
    print("✓ Queue locked")

    # Try to add cycle while locked
    cycle2 = Cycle(type="Baseline", length_minutes=1.0)
    result = presenter.add_cycle(cycle2)
    assert result == False, "Add should fail when locked"
    assert presenter.get_queue_size() == 1, "Queue size should not change"
    print("✓ Add blocked while locked")

    # Unlock queue
    presenter.unlock_queue()
    assert presenter.is_queue_locked() == False, "Queue should be unlocked"
    print("✓ Queue unlocked")

    # Now add should work
    result = presenter.add_cycle(cycle2)
    assert result == True, "Add should succeed when unlocked"
    assert presenter.get_queue_size() == 2, "Queue size should increase"
    print("✓ Add works after unlock")

    print("✅ Test 5 PASSED\n")


def test_execution_workflow():
    """Test execution workflow with pop and mark completed."""
    print("\n=== Test 6: Execution Workflow ===")

    presenter = QueuePresenter()

    # Add 3 cycles
    for i in range(1, 4):
        cycle = Cycle(type="Baseline", length_minutes=float(i))
        presenter.add_cycle(cycle)

    print(f"Queued 3 cycles, total duration: {presenter.get_total_duration():.1f} min")

    # Lock and execute first cycle
    presenter.lock_queue()
    cycle = presenter.pop_next_cycle()

    assert cycle is not None, "Should get next cycle"
    assert presenter.get_queue_size() == 2, "Queue should have 2 left"
    print(f"✓ Popped cycle: {cycle.name}, remaining: {presenter.get_queue_size()}")

    # Mark completed
    presenter.mark_cycle_completed(cycle)
    completed = presenter.get_completed_cycles()
    assert len(completed) == 1, "Should have 1 completed cycle"
    print(f"✓ Marked completed, history: {len(completed)}")

    # Unlock
    presenter.unlock_queue()

    print("✅ Test 6 PASSED\n")


def test_state_persistence():
    """Test state backup and restore through presenter."""
    print("\n=== Test 7: State Persistence ===")

    presenter = QueuePresenter()

    # Add cycles and complete one
    for i in range(3):
        cycle = Cycle(type="Baseline", length_minutes=1.0)
        presenter.add_cycle(cycle)

    # Pop and complete one
    cycle = presenter.pop_next_cycle()
    presenter.mark_cycle_completed(cycle)

    print(f"State: queue={presenter.get_queue_size()}, completed={len(presenter.get_completed_cycles())}")

    # Get state
    state = presenter.get_state()
    assert 'queue' in state, "State should have queue"
    assert 'completed' in state, "State should have completed"
    print(f"✓ Saved state: {len(state['queue'])} queued, {len(state['completed'])} completed")

    # Clear everything
    presenter.clear_queue()
    assert presenter.get_queue_size() == 0, "Queue should be empty"

    # Restore state
    result = presenter.restore_state(state)
    assert result == True, "Restore should succeed"
    assert presenter.get_queue_size() == 2, "Should restore 2 queued cycles"
    assert len(presenter.get_completed_cycles()) == 1, "Should restore 1 completed"
    print(f"✓ Restored: queue={presenter.get_queue_size()}, completed={len(presenter.get_completed_cycles())}")

    # History should be cleared after restore
    assert presenter.can_undo() == False, "Undo should be cleared"
    assert presenter.can_redo() == False, "Redo should be cleared"
    print("✓ Undo/redo history cleared on restore")

    print("✅ Test 7 PASSED\n")


def test_undo_redo_descriptions():
    """Test undo/redo description strings."""
    print("\n=== Test 8: Undo/Redo Descriptions ===")

    presenter = QueuePresenter()

    # Add cycle
    cycle = Cycle(type="Baseline", length_minutes=1.0)
    presenter.add_cycle(cycle)

    # Check undo description
    desc = presenter.get_undo_description()
    assert desc is not None, "Should have undo description"
    assert "Add" in desc or "Baseline" in desc, "Description should mention add or type"
    print(f"✓ Undo description: '{desc}'")

    # Undo
    presenter.undo()

    # Check redo description
    desc = presenter.get_redo_description()
    assert desc is not None, "Should have redo description"
    print(f"✓ Redo description: '{desc}'")

    # Clear all
    presenter.clear_history()
    assert presenter.get_undo_description() is None, "Should have no undo after clear"
    assert presenter.get_redo_description() is None, "Should have no redo after clear"
    print("✓ Descriptions cleared")

    print("✅ Test 8 PASSED\n")


def test_find_and_peek():
    """Test utility methods through presenter."""
    print("\n=== Test 9: Find and Peek Methods ===")

    presenter = QueuePresenter()

    # Add cycles
    cycle1 = Cycle(type="Baseline", length_minutes=1.0)
    cycle2 = Cycle(type="Association", length_minutes=2.0)
    presenter.add_cycle(cycle1)
    presenter.add_cycle(cycle2)

    # Get IDs
    cycles = presenter.get_queue_snapshot()
    id1, id2 = cycles[0].cycle_id, cycles[1].cycle_id
    print(f"Cycle IDs: {id1}, {id2}")

    # Find by ID
    found = presenter.find_cycle_by_id(id1)
    assert found is not None, "Should find cycle by ID"
    assert found.cycle_id == id1, "Should find correct cycle"
    print(f"✓ Found cycle {id1} by ID")

    # Peek next
    next_cycle = presenter.peek_next_cycle()
    assert next_cycle is not None, "Should peek next cycle"
    assert next_cycle.cycle_id == id1, "Next should be first cycle"
    assert presenter.get_queue_size() == 2, "Peek should not remove"
    print(f"✓ Peeked next: {next_cycle.name}, queue size unchanged")

    print("✅ Test 9 PASSED\n")


def test_presenter_stats():
    """Test presenter statistics/debugging info."""
    print("\n=== Test 10: Presenter Stats ===")

    presenter = QueuePresenter()

    # Add some cycles
    for i in range(3):
        cycle = Cycle(type="Baseline", length_minutes=1.0)
        presenter.add_cycle(cycle)

    # Get stats
    stats = presenter.get_stats()

    assert stats['queue_size'] == 3, "Stats should show 3 queued"
    assert stats['undo_count'] == 3, "Stats should show 3 undo ops"
    assert stats['is_locked'] == False, "Stats should show unlocked"
    assert stats['can_undo'] == True, "Stats should show can undo"
    print(f"✓ Stats: {stats}")

    # Check repr
    repr_str = repr(presenter)
    assert "QueuePresenter" in repr_str, "Repr should include class name"
    assert "queue=3" in repr_str, "Repr should show queue size"
    print(f"✓ Repr: {repr_str}")

    print("✅ Test 10 PASSED\n")


def run_all_tests():
    """Run all presenter tests."""
    print("="*70)
    print("QUEUE PRESENTER TEST SUITE")
    print("="*70)

    tests = [
        test_add_and_undo,
        test_signal_forwarding,
        test_bulk_operations,
        test_reorder_with_undo,
        test_queue_locking,
        test_execution_workflow,
        test_state_persistence,
        test_undo_redo_descriptions,
        test_find_and_peek,
        test_presenter_stats
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
        print("\n🎉 ALL TESTS PASSED! QueuePresenter is ready for integration.")
        print("\nNext steps:")
        print("  1. Create keyboard shortcuts (Ctrl+Z, Ctrl+Shift+Z)")
        print("  2. Add Undo/Redo toolbar buttons")
        print("  3. Proceed to Phase 4: Extract Queue Widgets")
        print("  4. Then Phase 5: Integrate with Application class")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
