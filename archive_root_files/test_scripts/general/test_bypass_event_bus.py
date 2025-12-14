"""
Test if event bus signal routing causes the crash
Bypass event bus and connect directly to see if it works
"""
import sys
sys.path.insert(0, r'c:\Users\ludol\ezControl-AI\Affilabs.core beta')

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, Qt
import time

print("=== TEST: BYPASS EVENT BUS ===\n")

# Import real Application class FIRST (before creating QApplication)
print("[1] Importing Application class...")
from main_simplified import Application

print("[2] Creating Application (full initialization)...")
real_app = Application(sys.argv)
print(f"[OK] Application created: {type(real_app).__name__}\n")

print("[3] Checking event bus connections...")
print(f"    event_bus exists: {hasattr(real_app, 'event_bus')}")
print(f"    data_mgr exists: {hasattr(real_app, 'data_mgr')}")
print(f"    _on_spectrum_acquired exists: {hasattr(real_app, '_on_spectrum_acquired')}")

# Test direct signal connection (bypass event bus)
print("\n[4] Testing DIRECT signal connection (bypass event bus)...")
try:
    # Disconnect event bus
    print("    Disconnecting event_bus.spectrum_acquired...")
    try:
        real_app.event_bus.spectrum_acquired.disconnect(real_app._on_spectrum_acquired)
        print("    [OK] Event bus disconnected")
    except:
        print("    [INFO] Event bus already disconnected or not connected")
    
    # Connect directly from data_mgr to _on_spectrum_acquired
    print("    Connecting data_mgr.spectrum_acquired DIRECTLY to _on_spectrum_acquired...")
    real_app.data_mgr.spectrum_acquired.connect(real_app._on_spectrum_acquired, Qt.QueuedConnection)
    print("    [OK] Direct connection established\n")
    
    print("="*60)
    print("DIRECT CONNECTION TEST COMPLETE")
    print("Now run the app normally and click Start")
    print("If it works, the event bus is the problem!")
    print("="*60)
    
except Exception as e:
    print(f"    [ERROR] Connection test failed: {e}")
    import traceback
    traceback.print_exc()

# Show window and run
real_app.main_window.show()

def check_status():
    print("\n[STATUS CHECK] App running with DIRECT signal connection (no event bus)")
    print("Click Start button to test if it works without event bus...")

QTimer.singleShot(2000, check_status)

sys.exit(real_app.exec())
