"""Test suite for QueueManager.

Tests all queue operations, locking, state persistence, and signal emissions.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from affilabs.managers.queue_manager import QueueManager
from affilabs.domain.cycle import Cycle


def test_add_cycle():
    """Test adding cycles to the queue."""
    print("\n🧪 Test 1: Add cycle")

    mgr = QueueManager()

    # Create test cycle
    cycle = Cycle(
        type='Baseline',
        length_minutes=5.0,
        name='Test Cycle',
        note='Testing add',
        status='pending'
    )

    # Add to queue
    result = mgr.add_cycle(cycle)

    assert result == True, "Add should succeed"
    assert mgr.get_queue_size() == 1, "Queue should have 1 cycle"
    assert cycle.cycle_id == 1, "First cycle should have ID 1"
    assert cycle.name == "Cycle 1", "Cycle should be renumbered"

    # Add another
    cycle2 = Cycle(type='Concentration', length_minutes=10.0, name='Test', note='', status='pending')
    mgr.add_cycle(cycle2)

    assert mgr.get_queue_size() == 2, "Queue should have 2 cycles"
    assert cycle2.cycle_id == 2, "Second cycle should have ID 2"
    assert cycle2.name == "Cycle 2", "Second cycle should be renumbered"

    print("   ✅ Add cycle works")
    print("   ✅ Auto ID assignment works")
    print("   ✅ Auto renumbering works")
    print("   ✅ Test 1 PASSED\n")


def test_delete_cycle():
    """Test deleting cycles from the queue."""
    print("🧪 Test 2: Delete cycle")

    mgr = QueueManager()

    # Add 3 cycles
    for i in range(3):
        cycle = Cycle(type='Baseline', length_minutes=5.0, name=f'C{i}', note='', status='pending')
        mgr.add_cycle(cycle)

    assert mgr.get_queue_size() == 3, "Should have 3 cycles"

    # Delete middle cycle
    deleted = mgr.delete_cycle(1)

    assert deleted is not None, "Delete should return cycle"
    assert deleted.cycle_id == 2, "Deleted cycle should have ID 2"
    assert mgr.get_queue_size() == 2, "Should have 2 cycles remaining"

    # Check renumbering
    queue = mgr.get_queue_snapshot()
    assert queue[0].name == "Cycle 1", "First cycle should be Cycle 1"
    assert queue[1].name == "Cycle 2", "Second cycle should be Cycle 2"
    assert queue[0].cycle_id == 1, "First cycle ID should still be 1"
    assert queue[1].cycle_id == 3, "Second cycle ID should still be 3 (no gaps)"

    print("   ✅ Delete cycle works")
    print("   ✅ Renumbering after delete works")
    print("   ✅ Cycle IDs preserved (gaps expected)")
    print("   ✅ Test 2 PASSED\n")


def test_bulk_delete():
    """Test deleting multiple cycles at once."""
    print("🧪 Test 3: Bulk delete")

    mgr = QueueManager()

    # Add 5 cycles
    for i in range(5):
        cycle = Cycle(type='Baseline', length_minutes=5.0, name=f'C{i}', note='', status='pending')
        mgr.add_cycle(cycle)

    # Delete cycles at indices 1, 2, 4
    deleted = mgr.delete_cycles([1, 2, 4])

    assert len(deleted) == 3, "Should delete 3 cycles"
    assert mgr.get_queue_size() == 2, "Should have 2 cycles remaining"

    # Check remaining cycles
    queue = mgr.get_queue_snapshot()
    assert queue[0].cycle_id == 1, "First remaining should be original cycle 1"
    assert queue[1].cycle_id == 4, "Second remaining should be original cycle 4"

    print("   ✅ Bulk delete works")
    print("   ✅ Correct cycles deleted")
    print("   ✅ Test 3 PASSED\n")


def test_reorder_cycle():
    """Test reordering cycles in the queue."""
    print("🧪 Test 4: Reorder cycle")

    mgr = QueueManager()

    # Add 4 cycles
    for i in range(4):
        cycle = Cycle(type='Baseline', length_minutes=5.0, name=f'C{i}', note='', status='pending')
        mgr.add_cycle(cycle)

    # Get original IDs
    original_ids = [c.cycle_id for c in mgr.get_queue_snapshot()]

    # Move cycle from position 0 to position 2
    result = mgr.reorder_cycle(0, 2)

    assert result == True, "Reorder should succeed"

    # Check new order
    queue = mgr.get_queue_snapshot()
    assert queue[0].cycle_id == original_ids[1], "Position 0 should now be old position 1"
    assert queue[1].cycle_id == original_ids[2], "Position 1 should now be old position 2"
    assert queue[2].cycle_id == original_ids[0], "Position 2 should now be old position 0"
    assert queue[3].cycle_id == original_ids[3], "Position 3 unchanged"

    # Check renumbering
    assert queue[0].name == "Cycle 1", "Should be renumbered to Cycle 1"
    assert queue[2].name == "Cycle 3", "Should be renumbered to Cycle 3"

    print("   ✅ Reorder cycle works")
    print("   ✅ IDs preserved after reorder")
    print("   ✅ Renumbering after reorder works")
    print("   ✅ Test 4 PASSED\n")


def test_queue_locking():
    """Test queue locking mechanism."""
    print("🧪 Test 5: Queue locking")

    mgr = QueueManager()

    # Add a cycle
    cycle = Cycle(type='Baseline', length_minutes=5.0, name='Test', note='', status='pending')
    mgr.add_cycle(cycle)

    assert mgr.is_locked() == False, "Queue should start unlocked"

    # Lock queue
    mgr.lock()
    assert mgr.is_locked() == True, "Queue should be locked"

    # Try to add while locked
    cycle2 = Cycle(type='Baseline', length_minutes=5.0, name='Test2', note='', status='pending')
    result = mgr.add_cycle(cycle2)
    assert result == False, "Add should fail when locked"
    assert mgr.get_queue_size() == 1, "Queue size should not change"

    # Try to delete while locked
    deleted = mgr.delete_cycle(0)
    assert deleted is None, "Delete should fail when locked"
    assert mgr.get_queue_size() == 1, "Queue size should not change"

    # Try to reorder while locked
    result = mgr.reorder_cycle(0, 0)
    assert result == False, "Reorder should fail when locked"

    # Unlock and try again
    mgr.unlock()
    assert mgr.is_locked() == False, "Queue should be unlocked"

    result = mgr.add_cycle(cycle2)
    assert result == True, "Add should succeed after unlock"
    assert mgr.get_queue_size() == 2, "Queue should now have 2 cycles"

    print("   ✅ Lock/unlock works")
    print("   ✅ Operations blocked when locked")
    print("   ✅ Operations allowed when unlocked")
    print("   ✅ Test 5 PASSED\n")


def test_pop_and_completed():
    """Test popping cycles and marking as completed."""
    print("🧪 Test 6: Pop and completed cycles")

    mgr = QueueManager()

    # Add 3 cycles
    for i in range(3):
        cycle = Cycle(type='Baseline', length_minutes=5.0, name=f'C{i}', note='', status='pending')
        mgr.add_cycle(cycle)

    # Pop first cycle
    popped = mgr.pop_next_cycle()

    assert popped is not None, "Pop should return cycle"
    assert popped.cycle_id == 1, "Popped cycle should be first one"
    assert mgr.get_queue_size() == 2, "Queue should have 2 cycles remaining"

    # Mark as completed
    mgr.mark_completed(popped)
    assert mgr.get_completed_count() == 1, "Should have 1 completed cycle"

    # Pop and complete remaining
    while not mgr.is_empty():
        cycle = mgr.pop_next_cycle()
        mgr.mark_completed(cycle)

    assert mgr.get_queue_size() == 0, "Queue should be empty"
    assert mgr.get_completed_count() == 3, "Should have 3 completed cycles"

    # Get completed list
    completed = mgr.get_completed_cycles()
    assert len(completed) == 3, "Should return all completed cycles"

    print("   ✅ Pop next cycle works")
    print("   ✅ Mark completed works")
    print("   ✅ Completed cycles tracking works")
    print("   ✅ Test 6 PASSED\n")


def test_state_persistence():
    """Test saving and restoring queue state."""
    print("🧪 Test 7: State persistence")

    mgr1 = QueueManager()

    # Add cycles and mark some completed
    for i in range(3):
        cycle = Cycle(type='Baseline', length_minutes=5.0, name=f'C{i}', note=f'Note {i}', status='pending')
        mgr1.add_cycle(cycle)

    completed_cycle = mgr1.pop_next_cycle()
    mgr1.mark_completed(completed_cycle)

    # Get state
    state = mgr1.get_state()

    assert 'queue' in state, "State should have queue"
    assert 'completed' in state, "State should have completed"
    assert 'cycle_counter' in state, "State should have counter"
    assert len(state['queue']) == 2, "State should have 2 queued cycles"
    assert len(state['completed']) == 1, "State should have 1 completed cycle"
    assert state['cycle_counter'] == 3, "Counter should be 3"

    # Create new manager and restore
    mgr2 = QueueManager()
    mgr2.restore_state(state)

    assert mgr2.get_queue_size() == 2, "Restored queue should have 2 cycles"
    assert mgr2.get_completed_count() == 1, "Restored should have 1 completed"
    assert mgr2._cycle_counter == 3, "Counter should be restored"

    # Verify data integrity
    restored_queue = mgr2.get_queue_snapshot()
    assert restored_queue[0].note == 'Note 1', "Cycle data should be preserved"

    # Add new cycle to verify counter works
    new_cycle = Cycle(type='Baseline', length_minutes=5.0, name='New', note='', status='pending')
    mgr2.add_cycle(new_cycle)
    assert new_cycle.cycle_id == 4, "Next ID should be 4 (no collisions)"

    print("   ✅ Get state works")
    print("   ✅ Restore state works")
    print("   ✅ Data integrity preserved")
    print("   ✅ Counter continuity maintained")
    print("   ✅ Test 7 PASSED\n")


def test_utility_methods():
    """Test utility methods like total duration, find by ID."""
    print("🧪 Test 8: Utility methods")

    mgr = QueueManager()

    # Add cycles with different durations
    c1 = Cycle(type='Baseline', length_minutes=5.0, name='C1', note='', status='pending')
    c2 = Cycle(type='Concentration', length_minutes=10.0, name='C2', note='', status='pending')
    c3 = Cycle(type='Wash', length_minutes=2.0, name='C3', note='', status='pending')

    mgr.add_cycle(c1)
    mgr.add_cycle(c2)
    mgr.add_cycle(c3)

    # Test total duration
    total = mgr.get_total_duration()
    assert total == 17.0, f"Total duration should be 17.0, got {total}"

    # Test find by ID
    found = mgr.find_cycle_by_id(2)
    assert found is not None, "Should find cycle with ID 2"
    assert found.type == 'Concentration', "Found cycle should be Concentration type"

    # Test peek without removing
    peeked = mgr.peek_next_cycle()
    assert peeked is not None, "Peek should return cycle"
    assert peeked.cycle_id == 1, "Peeked cycle should be first one"
    assert mgr.get_queue_size() == 3, "Queue size should not change after peek"

    # Test get cycle at index
    cycle_at_1 = mgr.get_cycle_at(1)
    assert cycle_at_1.cycle_id == 2, "Cycle at index 1 should have ID 2"

    print("   ✅ Total duration calculation works")
    print("   ✅ Find by ID works")
    print("   ✅ Peek next works")
    print("   ✅ Get cycle at index works")
    print("   ✅ Test 8 PASSED\n")


def test_signal_emissions():
    """Test that signals are emitted correctly."""
    print("🧪 Test 9: Signal emissions")

    mgr = QueueManager()

    # Track signal emissions
    signals_received = {
        'queue_changed': 0,
        'cycle_added': 0,
        'cycle_deleted': 0,
        'cycle_reordered': 0,
        'queue_locked': 0,
        'queue_unlocked': 0,
    }

    # Connect signal handlers
    mgr.queue_changed.connect(lambda: signals_received.__setitem__('queue_changed', signals_received['queue_changed'] + 1))
    mgr.cycle_added.connect(lambda c: signals_received.__setitem__('cycle_added', signals_received['cycle_added'] + 1))
    mgr.cycle_deleted.connect(lambda i, c: signals_received.__setitem__('cycle_deleted', signals_received['cycle_deleted'] + 1))
    mgr.cycle_reordered.connect(lambda f, t: signals_received.__setitem__('cycle_reordered', signals_received['cycle_reordered'] + 1))
    mgr.queue_locked.connect(lambda: signals_received.__setitem__('queue_locked', signals_received['queue_locked'] + 1))
    mgr.queue_unlocked.connect(lambda: signals_received.__setitem__('queue_unlocked', signals_received['queue_unlocked'] + 1))

    # Add cycle - should emit cycle_added and queue_changed
    cycle = Cycle(type='Baseline', length_minutes=5.0, name='Test', note='', status='pending')
    mgr.add_cycle(cycle)

    assert signals_received['cycle_added'] == 1, "Should emit cycle_added"
    assert signals_received['queue_changed'] >= 1, "Should emit queue_changed"

    # Lock - should emit queue_locked
    mgr.lock()
    assert signals_received['queue_locked'] == 1, "Should emit queue_locked"

    # Unlock - should emit queue_unlocked
    mgr.unlock()
    assert signals_received['queue_unlocked'] == 1, "Should emit queue_unlocked"

    # Add another cycle
    mgr.add_cycle(Cycle(type='Baseline', length_minutes=5.0, name='Test2', note='', status='pending'))

    # Delete - should emit cycle_deleted and queue_changed
    deleted_count_before = signals_received['cycle_deleted']
    mgr.delete_cycle(0)
    assert signals_received['cycle_deleted'] == deleted_count_before + 1, "Should emit cycle_deleted"

    # Reorder - should emit cycle_reordered and queue_changed
    mgr.add_cycle(Cycle(type='Baseline', length_minutes=5.0, name='Test3', note='', status='pending'))
    reordered_count_before = signals_received['cycle_reordered']
    mgr.reorder_cycle(0, 1)
    assert signals_received['cycle_reordered'] == reordered_count_before + 1, "Should emit cycle_reordered"

    print("   ✅ cycle_added signal emitted")
    print("   ✅ cycle_deleted signal emitted")
    print("   ✅ cycle_reordered signal emitted")
    print("   ✅ queue_locked signal emitted")
    print("   ✅ queue_unlocked signal emitted")
    print("   ✅ queue_changed signal emitted")
    print("   ✅ Test 9 PASSED\n")


def run_all_tests():
    """Run all QueueManager tests."""
    print("=" * 80)
    print("QUEUEMANAGER TEST SUITE")
    print("=" * 80)

    try:
        test_add_cycle()
        test_delete_cycle()
        test_bulk_delete()
        test_reorder_cycle()
        test_queue_locking()
        test_pop_and_completed()
        test_state_persistence()
        test_utility_methods()
        test_signal_emissions()

        print("=" * 80)
        print("✅ ALL TESTS PASSED!")
        print("=" * 80)
        print("\nQueueManager is ready for integration:")
        print("  ✅ CRUD operations work correctly")
        print("  ✅ Locking mechanism prevents race conditions")
        print("  ✅ State persistence for crash recovery")
        print("  ✅ Signals emit for UI updates")
        print("  ✅ Bulk operations supported")
        print("  ✅ ID management prevents collisions")
        print("\nReady to proceed to Step 2: CommandHistory")

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        raise
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == '__main__':
    run_all_tests()
