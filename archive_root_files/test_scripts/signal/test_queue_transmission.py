"""Test the _queue_transmission_update method specifically
This is called on line 1058 right before the crash
"""

import sys

import numpy as np
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

print("=== TEST: _queue_transmission_update METHOD ===\n")

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

import sys

sys.path.insert(0, r"c:\Users\ludol\ezControl-AI\Affilabs.core beta")
from affilabs_core_ui import AffilabsMainWindow
from core.data_buffer_manager import DataBufferManager

print("[1] Creating main window...")
main_window = AffilabsMainWindow()
main_window.show()
print("[OK] Main window created\n")

print("[2] Creating buffer manager...")
buffer_mgr = DataBufferManager()
print("[OK] Buffer manager created\n")

# Create fake spectrum data (like what acquisition sends)
print("[3] Creating fake spectrum data...")
fake_wavelengths = np.linspace(200, 1100, 2048)
fake_intensities = np.random.randint(1000, 50000, 2048)
full_spectrum = {
    "wavelengths": fake_wavelengths,
    "intensities": fake_intensities,
}
print(f"[OK] Spectrum data: {len(fake_wavelengths)} wavelengths\n")

# Build data dict like _process_spectrum_data receives
print("[4] Building data dict (like acquisition sends)...")
data = {
    "channel": "a",
    "elapsed_time": 0.0,
    "full_spectrum": full_spectrum,  # This is the key - needs full spectrum
}
print(f"[OK] Data dict: channel={data['channel']}, time={data['elapsed_time']}\n")

# Now test _queue_transmission_update
print("[5] Testing _queue_transmission_update...")
try:
    # Check if app exists (should be set by Application.__init__)
    if hasattr(main_window, "app") and main_window.app:
        print(f"    main_window.app exists: {type(main_window.app).__name__}")

        # Check if method exists on app
        if hasattr(main_window.app, "_queue_transmission_update"):
            print("    Method _queue_transmission_update found on app")

            # Try calling it
            print(
                f"    Calling app._queue_transmission_update('{data['channel']}', data)...",
            )
            main_window.app._queue_transmission_update(data["channel"], data)
            print("    [OK] Method call succeeded!")
        else:
            print("    [ERROR] Method not found on app")
            print(
                f"    Available methods: {[m for m in dir(main_window.app) if 'transmission' in m.lower()]}",
            )
    else:
        print("    [ERROR] main_window.app not set (app not initialized)")
        print(
            "    This is expected in this test - real app sets it in Application.__init__",
        )

except Exception as e:
    print(f"    [ERROR] Method call crashed: {e}")
    import traceback

    traceback.print_exc()

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)


# Keep window open briefly
def shutdown():
    app.quit()


QTimer.singleShot(2000, shutdown)
sys.exit(app.exec())
