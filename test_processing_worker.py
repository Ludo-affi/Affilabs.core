"""
Test the _processing_worker thread that calls _process_spectrum_data
Focus on what happens AFTER the function returns
"""
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from queue import Queue
import threading
import time

print("=== TEST: PROCESSING WORKER THREAD ===\n")

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

import sys
sys.path.insert(0, r'c:\Users\ludol\ezControl-AI\Affilabs.core beta')
from affilabs_core_ui import AffilabsMainWindow

print("[1] Creating main window...")
main_window = AffilabsMainWindow()
main_window.show()
print("[OK] Main window created\n")

# Create fake spectrum queue
print("[2] Creating spectrum queue...")
_spectrum_queue = Queue(maxsize=200)
print("[OK] Queue created\n")

# Simulate _processing_worker behavior
def fake_processing_worker():
    """Simulate the worker thread that processes spectra"""
    print("[WORKER] Processing worker started")
    
    # Put fake data in queue
    fake_data = {
        'channel': 'a',
        'wavelength': 648.3,
        'intensity': 6076,
        'elapsed_time': 0.0,
        'full_spectrum': None
    }
    
    print(f"[WORKER] Putting data in queue: {fake_data}")
    _spectrum_queue.put(fake_data)
    
    time.sleep(0.1)  # Small delay
    
    print("[WORKER] Getting data from queue...")
    data = _spectrum_queue.get()
    print(f"[WORKER] Got data: channel={data['channel']}, wave={data['wavelength']}")
    
    print("[WORKER] Calling _process_spectrum_data...")
    try:
        # Check if method exists
        if hasattr(main_window, '_process_spectrum_data'):
            main_window._process_spectrum_data(data)
            print("[WORKER] _process_spectrum_data returned successfully")
        else:
            print("[WORKER ERROR] _process_spectrum_data method not found")
            print(f"[WORKER] Available methods: {[m for m in dir(main_window) if 'process' in m.lower()]}")
            
    except Exception as e:
        print(f"[WORKER ERROR] _process_spectrum_data crashed: {e}")
        import traceback
        traceback.print_exc()
    
    print("[WORKER] Continuing worker loop...")
    time.sleep(0.1)
    
    print("[WORKER] Worker thread exiting normally")

# Start worker thread
print("[3] Starting processing worker thread...")
worker = threading.Thread(target=fake_processing_worker, daemon=True)
worker.start()
print("[OK] Worker started\n")

# Keep app alive
def shutdown():
    print("\n[MAIN] Shutdown timer triggered")
    if worker.is_alive():
        print("[MAIN] Worker thread still running")
        worker.join(timeout=1.0)
    print("[MAIN] Exiting")
    app.quit()

QTimer.singleShot(3000, shutdown)

print("[MAIN] Running Qt event loop...\n")
sys.exit(app.exec())
