"""Test UI processing separately - isolate the crash in main_simplified.py processing."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

print("=" * 70)
print("UI PROCESSING CRASH TEST")
print("=" * 70)

import time

from PySide6.QtWidgets import QApplication

# Import the main window and dependencies
print("\n[1/5] Creating Qt application...")
app = QApplication(sys.argv)

print("[2/5] Importing MainWindow...")
from affilabs_core_ui import AffilabsMainWindow

print("[3/5] Creating main window (this takes a few seconds)...")
main_window = AffilabsMainWindow()
print("[OK] Main window created")

print("\n[4/5] Importing data buffer manager...")
from core.data_buffer_manager import DataBufferManager

print("[5/5] Creating buffer manager...")
buffer_mgr = DataBufferManager()
print("[OK] Buffer manager created")

# Simulate the processing that happens in main_simplified._process_spectrum_data
print("\n" + "=" * 70)
print("SIMULATING SPECTRUM DATA PROCESSING")
print("=" * 70)

# Create fake spectrum data (same format as real acquisition)
test_data = {
    "channel": "a",
    "wavelength": 651.2,
    "intensity": 6110,
    "timestamp": time.time(),
    "elapsed_time": 0.0,
    "is_preview": False,
    "full_spectrum": None,  # No full spectrum yet
    "transmission_spectrum": None,
}

print(f"\n[TEST 1] Processing Channel A data: wave={test_data['wavelength']}nm")

try:
    channel = test_data["channel"]
    elapsed_time = test_data["elapsed_time"]
    wavelength = test_data["wavelength"]

    print(
        f"[TEST 1a] Appending to buffer: ch={channel}, time={elapsed_time}, wave={wavelength}",
    )
    buffer_mgr.append_timeline_point(channel, elapsed_time, wavelength)
    print("[OK] Buffer append successful")

except Exception as e:
    print(f"[FAIL] Buffer append failed: {e}")
    import traceback

    traceback.print_exc()

# Test 2: Check if main_window has the attributes we're trying to access
print("\n[TEST 2] Checking main_window attributes...")
try:
    has_live_data = hasattr(main_window, "live_data_enabled")
    print(f"   live_data_enabled exists: {has_live_data}")
    if has_live_data:
        print(f"   live_data_enabled value: {main_window.live_data_enabled}")

    has_timeline_graph = hasattr(main_window, "full_timeline_graph")
    print(f"   full_timeline_graph exists: {has_timeline_graph}")

    if has_timeline_graph:
        has_cursor = hasattr(main_window.full_timeline_graph, "stop_cursor")
        print(f"   stop_cursor exists: {has_cursor}")

        if has_cursor:
            cursor = main_window.full_timeline_graph.stop_cursor
            print(f"   stop_cursor value: {cursor}")
            if cursor:
                print("[TEST 2a] Trying to set cursor value...")
                cursor.setValue(elapsed_time)
                print("[OK] Cursor setValue successful")

except Exception as e:
    print(f"[FAIL] Cursor test failed: {e}")
    import traceback

    traceback.print_exc()

# Test 3: Try _queue_transmission_update equivalent
print("\n[TEST 3] Testing transmission queue logic...")
if (
    test_data.get("full_spectrum") is not None
    and test_data.get("transmission_spectrum") is not None
):
    print("   Would queue transmission update (but data is None, so skipped)")
else:
    print("   [OK] Transmission queue skipped (no full spectrum)")

print("\n" + "=" * 70)
print("UI PROCESSING TEST COMPLETE")
print("=" * 70)
print("\nIf you see this, the UI processing doesn't crash!")
print("The crash must be elsewhere in main_simplified.py")

# Keep app alive briefly
print("\n[CLEANUP] Closing in 2 seconds...")
time.sleep(2)

sys.exit(0)
