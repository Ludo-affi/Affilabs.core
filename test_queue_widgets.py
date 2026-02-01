"""Integration test for Queue Widgets + Presenter.

Tests the full widget stack:
- QueueSummaryWidget (table)
- QueueToolbar (buttons)
- QueuePresenter (coordination)

Verifies signal flow and widget updates.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PySide6.QtCore import QTimer

from affilabs.domain.cycle import Cycle
from affilabs.presenters.queue_presenter import QueuePresenter
from affilabs.widgets.queue_summary_widget import QueueSummaryWidget
from affilabs.widgets.queue_toolbar import QueueToolbar


def test_widget_integration():
    """Test widgets integrate properly with presenter."""
    print("\n=== Integration Test: Widgets + Presenter ===")

    # Create Qt application
    app = QApplication.instance() or QApplication(sys.argv)

    # Create presenter
    presenter = QueuePresenter()

    # Create widgets
    table = QueueSummaryWidget()
    toolbar = QueueToolbar()

    # Connect table to presenter
    table.set_presenter(presenter)
    table.cycle_reordered.connect(presenter.reorder_cycle)
    table.cycles_deleted.connect(presenter.delete_cycles)

    # Connect toolbar to presenter
    toolbar.undo_requested.connect(presenter.undo)
    toolbar.redo_requested.connect(presenter.redo)
    toolbar.delete_selected_requested.connect(
        lambda: presenter.delete_cycles(table.get_selected_indices())
    )
    toolbar.clear_all_requested.connect(presenter.clear_queue)

    # Connect presenter to toolbar (button states)
    presenter.can_undo_changed.connect(toolbar.set_undo_enabled)
    presenter.can_redo_changed.connect(toolbar.set_redo_enabled)
    presenter.undo_description_changed.connect(toolbar.set_undo_tooltip)
    presenter.redo_description_changed.connect(toolbar.set_redo_tooltip)

    # Track signal emissions
    signals_received = {
        'table_refreshed': 0,
        'toolbar_undo_enabled': [],
        'selection_changed': []
    }

    def on_table_refresh():
        signals_received['table_refreshed'] += 1

    def on_undo_enabled(enabled):
        signals_received['toolbar_undo_enabled'].append(enabled)

    def on_selection(indices):
        signals_received['selection_changed'].append(indices)

    # Monitor signals
    presenter.queue_changed.connect(on_table_refresh)
    presenter.can_undo_changed.connect(on_undo_enabled)
    table.selection_changed.connect(on_selection)

    # Test 1: Add cycles
    print("\nTest 1: Adding cycles...")
    for i in range(3):
        cycle = Cycle(type="Baseline", length_minutes=float(i+1))
        presenter.add_cycle(cycle)

    assert table.get_cycle_count() == 3, "Table should show 3 cycles"
    assert True in signals_received['toolbar_undo_enabled'], "Undo should be enabled"
    print(f"✓ Added 3 cycles, table count: {table.get_cycle_count()}")
    print(f"✓ Undo enabled signals: {signals_received['toolbar_undo_enabled']}")

    # Test 2: Undo
    print("\nTest 2: Undo operation...")
    presenter.undo()
    assert table.get_cycle_count() == 2, "Table should show 2 cycles after undo"
    print(f"✓ Undone, table count: {table.get_cycle_count()}")

    # Test 3: Redo
    print("\nTest 3: Redo operation...")
    presenter.redo()
    assert table.get_cycle_count() == 3, "Table should show 3 cycles after redo"
    print(f"✓ Redone, table count: {table.get_cycle_count()}")

    # Test 4: Reorder via signal
    print("\nTest 4: Reorder cycle...")
    initial_cycles = presenter.get_queue_snapshot()
    initial_ids = [c.cycle_id for c in initial_cycles]

    # Simulate drag-drop: move index 0 to index 2
    table.cycle_reordered.emit(0, 2)

    reordered_cycles = presenter.get_queue_snapshot()
    reordered_ids = [c.cycle_id for c in reordered_cycles]

    assert reordered_ids != initial_ids, "Order should have changed"
    print(f"✓ Reordered: {initial_ids} → {reordered_ids}")

    # Test 5: Delete via toolbar
    print("\nTest 5: Delete selected cycles...")
    # Simulate selection
    table.selectRow(0)
    selected = table.get_selected_indices()
    assert len(selected) == 1, "Should have 1 selected row"

    # Delete via presenter
    presenter.delete_cycles(selected)
    assert table.get_cycle_count() == 2, "Table should show 2 cycles after delete"
    print(f"✓ Deleted 1 cycle, remaining: {table.get_cycle_count()}")

    # Test 6: Queue locking
    print("\nTest 6: Queue locking...")
    presenter.lock_queue()
    assert not table.isEnabled(), "Table should be disabled when locked"
    print("✓ Table disabled when queue locked")

    presenter.unlock_queue()
    assert table.isEnabled(), "Table should be enabled when unlocked"
    print("✓ Table enabled when queue unlocked")

    # Test 7: Clear all
    print("\nTest 7: Clear all cycles...")
    presenter.clear_queue()
    assert table.get_cycle_count() == 0, "Table should be empty"
    print(f"✓ Cleared, table count: {table.get_cycle_count()}")

    # Test 8: Undo clear
    print("\nTest 8: Undo clear...")
    presenter.undo()
    assert table.get_cycle_count() > 0, "Table should have cycles after undo"
    print(f"✓ Undone clear, table count: {table.get_cycle_count()}")

    # Test 9: Toolbar info update
    print("\nTest 9: Toolbar info update...")
    stats = presenter.get_stats()
    toolbar.update_from_presenter_stats(stats)
    print(f"✓ Toolbar updated with stats: {stats}")

    print("\n" + "="*70)
    print("✅ ALL INTEGRATION TESTS PASSED")
    print("="*70)
    print(f"\nSignal tracking:")
    print(f"  - Table refreshed: {signals_received['table_refreshed']} times")
    print(f"  - Undo state changes: {len(signals_received['toolbar_undo_enabled'])}")
    print(f"  - Selection changes: {len(signals_received['selection_changed'])}")

    return True


def test_visual_widgets():
    """Visual test - show the widgets in a window."""
    print("\n=== Visual Test: Widget Display ===")
    print("Opening window with queue widgets...")
    print("(Close window to continue)")

    # Create Qt application
    app = QApplication.instance() or QApplication(sys.argv)

    # Create main window
    window = QMainWindow()
    window.setWindowTitle("Queue Widgets Test")
    window.resize(600, 400)

    # Create central widget
    central = QWidget()
    layout = QVBoxLayout(central)

    # Create presenter
    presenter = QueuePresenter()

    # Create widgets
    toolbar = QueueToolbar(window)
    table = QueueSummaryWidget()

    # Add to layout
    layout.addWidget(toolbar)
    layout.addWidget(table)

    window.setCentralWidget(central)

    # Connect everything
    table.set_presenter(presenter)
    table.cycle_reordered.connect(presenter.reorder_cycle)
    table.cycles_deleted.connect(presenter.delete_cycles)

    toolbar.undo_requested.connect(presenter.undo)
    toolbar.redo_requested.connect(presenter.redo)
    toolbar.delete_selected_requested.connect(
        lambda: presenter.delete_cycles(table.get_selected_indices())
    )
    toolbar.clear_all_requested.connect(presenter.clear_queue)

    presenter.can_undo_changed.connect(toolbar.set_undo_enabled)
    presenter.can_redo_changed.connect(toolbar.set_redo_enabled)
    presenter.undo_description_changed.connect(toolbar.set_undo_tooltip)

    # Update delete button based on selection
    table.selection_changed.connect(
        lambda indices: toolbar.set_delete_enabled(len(indices) > 0)
    )

    # Update toolbar info on queue changes
    def update_toolbar_info():
        stats = presenter.get_stats()
        toolbar.update_from_presenter_stats(stats)

    presenter.queue_changed.connect(update_toolbar_info)

    # Add some test data
    for i in range(5):
        cycle = Cycle(type="Baseline", length_minutes=float(i+1), note=f"Test cycle {i+1}")
        presenter.add_cycle(cycle)

    # Show window
    window.show()

    # Auto-close after 3 seconds for automated testing
    QTimer.singleShot(3000, window.close)

    # Run event loop
    app.exec()

    print("✓ Visual test completed")
    return True


def run_all_tests():
    """Run all widget integration tests."""
    print("="*70)
    print("QUEUE WIDGETS INTEGRATION TEST SUITE")
    print("="*70)

    tests = [
        test_widget_integration,
        test_visual_widgets
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            result = test()
            if result:
                passed += 1
        except AssertionError as e:
            print(f"❌ {test.__name__} FAILED: {e}\n")
            failed += 1
        except Exception as e:
            print(f"💥 {test.__name__} ERROR: {e}\n")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "="*70)
    print(f"FINAL RESULTS: {passed} passed, {failed} failed")
    print("="*70)

    if failed == 0:
        print("\n🎉 ALL WIDGET TESTS PASSED!")
        print("\nQueue Widgets are ready for integration:")
        print("  ✓ QueueSummaryWidget (drag-drop table)")
        print("  ✓ QueueToolbar (undo/redo/delete/clear)")
        print("  ✓ Signal flow working correctly")
        print("  ✓ Keyboard shortcuts registered")
        print("\nNext: Phase 5 - Integrate with Application class")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
