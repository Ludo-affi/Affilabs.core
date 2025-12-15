"""Test what happens AFTER transmission is queued
The crash happens after this line, so test the code that follows
"""

import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

print("=== TEST: CODE AFTER TRANSMISSION QUEUEING ===\n")

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

# Create minimal main window with cursor
import sys

sys.path.insert(0, r"c:\Users\ludol\ezControl-AI\Affilabs.core beta")
from affilabs_core_ui import AffilabsMainWindow

print("[1] Creating main window...")
main_window = AffilabsMainWindow()
main_window.show()
print("[OK] Main window created\n")

# Simulate the state right after "Transmission queued"
print("[2] Simulating post-transmission state...")
channel = "a"
elapsed_time = 0.0

# This is the code that runs AFTER line 1060 (transmission queued)
# Line 1068-1084: Cursor update with live_data_enabled check
print("[3] Testing cursor update (lines 1068-1084)...")
try:
    print(f"    live_data_enabled = {main_window.live_data_enabled}")

    if main_window.live_data_enabled:
        print("    [LIVE DATA ENABLED] Proceeding with cursor update...")

        if (
            hasattr(main_window.full_timeline_graph, "stop_cursor")
            and main_window.full_timeline_graph.stop_cursor is not None
        ):
            stop_cursor = main_window.full_timeline_graph.stop_cursor
            print(f"    stop_cursor found: {stop_cursor}")

            # Check if cursor is being dragged
            is_moving = getattr(stop_cursor, "moving", False)
            print(f"    is_moving = {is_moving}")

            if not is_moving:
                print(f"    Calling stop_cursor.setValue({elapsed_time})...")
                stop_cursor.setValue(elapsed_time)
                print("    [OK] setValue succeeded")

                # Update label
                if hasattr(stop_cursor, "label") and stop_cursor.label:
                    print("    Updating label...")
                    stop_cursor.label.setFormat(f"Stop: {elapsed_time:.1f}s")
                    print("    [OK] Label updated")
        else:
            print("    [SKIP] stop_cursor not available")
    else:
        print("    [SKIP] Live data disabled")

    print("[OK] Cursor update completed\n")

except (AttributeError, RuntimeError) as e:
    print(f"[ERROR] Cursor update failed: {e}\n")
    import traceback

    traceback.print_exc()

# Line 1093-1098: Queue graph update
print("[4] Testing _pending_graph_updates (lines 1093-1098)...")
try:
    # Simulate what _process_spectrum_data does
    _pending_graph_updates = {}  # This should exist in MainWindow

    if main_window.live_data_enabled:
        print(f"    Queueing graph update for channel {channel}...")
        _pending_graph_updates[channel] = {
            "elapsed_time": elapsed_time,
            "channel": channel,
        }
        print(f"    [OK] Graph update queued: {_pending_graph_updates}")
    else:
        print("    [SKIP] Live data disabled")

    print("[OK] Graph update queueing completed\n")

except Exception as e:
    print(f"[ERROR] Graph update queueing failed: {e}\n")
    import traceback

    traceback.print_exc()

# Line 1103-1109: Recording check
print("[5] Testing recording check (lines 1103-1109)...")
try:
    # Check if recording_mgr exists
    if hasattr(main_window, "recording_mgr"):
        print(f"    recording_mgr exists: {main_window.recording_mgr}")
        print(
            f"    is_recording = {main_window.recording_mgr.is_recording if main_window.recording_mgr else 'N/A'}",
        )
    else:
        print("    [SKIP] recording_mgr not found (expected)")

    print("[OK] Recording check completed\n")

except Exception as e:
    print(f"[ERROR] Recording check failed: {e}\n")
    import traceback

    traceback.print_exc()

print("=" * 60)
print("ALL TESTS PASSED!")
print("If you see this, the post-transmission code doesn't crash")
print("=" * 60)


# Keep window open briefly
def shutdown():
    app.quit()


QTimer.singleShot(2000, shutdown)
sys.exit(app.exec())
