"""Minimal acquisition test - bypasses UI completely for fast iteration."""

import sys
import time
import threading
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 70)
print("MINIMAL ACQUISITION TEST")
print("=" * 70)

# Initialize Qt first (required for hardware manager)
from PySide6.QtWidgets import QApplication
print("\n[1/6] Creating Qt application...")
app = QApplication(sys.argv)

# Import hardware and acquisition managers
from core.hardware_manager import HardwareManager
from core.data_acquisition_manager import DataAcquisitionManager

print("[2/6] Creating hardware manager...")
hardware_mgr = HardwareManager()

print("[3/6] Scanning for hardware...")

# Track scan completion
import threading
from PySide6.QtCore import QTimer
scan_complete = threading.Event()
scan_result = {'success': False}

def on_hardware_connected(status):
    scan_result['success'] = True
    scan_result['status'] = status
    scan_complete.set()
    print(f"   [OK] Hardware scan complete")
    # Don't call app.quit() here - let the test control the event loop

hardware_mgr.hardware_connected.connect(on_hardware_connected)
hardware_mgr.scan_and_connect()

# Run event loop until scan completes
while not scan_complete.is_set():
    app.processEvents()
    time.sleep(0.1)

if not scan_result['success']:
    print("[FAIL] Hardware scan unsuccessful")
    sys.exit(1)

time.sleep(1)  # Let hardware settle

if not hardware_mgr.ctrl or not hardware_mgr.usb:
    print("[FAIL] No hardware found")
    print(f"   ctrl: {hardware_mgr.ctrl}")
    print(f"   usb: {hardware_mgr.usb}")
    sys.exit(1)

print(f"[OK] Hardware found: ctrl={hardware_mgr.ctrl is not None}, usb={hardware_mgr.usb is not None}")

print("\n[4/6] Creating data acquisition manager...")
data_mgr = DataAcquisitionManager(hardware_mgr)

print("[5/6] Setting up fake calibration data (skip real calibration)...")
# Inject fake calibration data to bypass calibration
data_mgr.wave_data = list(range(200, 1100))  # Fake wavelengths
data_mgr.leds_calibrated = ['a', 'b', 'c', 'd']
data_mgr.led_intensity = {'a': 255, 'b': 255, 'c': 255, 'd': 255}
data_mgr.integration_time = 40  # ms
data_mgr.num_scans = 5  # Number of scans to average
data_mgr.calibrated = True  # Mark as calibrated
# Add fake ref_sig (S-reference spectra for each channel)
import numpy as np
fake_spectrum = np.ones(900) * 30000  # Fake reference intensity
data_mgr.ref_sig = {'a': fake_spectrum, 'b': fake_spectrum, 'c': fake_spectrum, 'd': fake_spectrum}
data_mgr.dark_sig = {'a': np.zeros(900), 'b': np.zeros(900), 'c': np.zeros(900), 'd': np.zeros(900)}
print("   [OK] Fake calibration data injected")

print("\n[6/6] Starting acquisition worker...")
print("=" * 70)

# Start acquisition
try:
    data_mgr.start_acquisition()

    # Let it run for 10 seconds
    print("\n[TEST] Running acquisition for 10 seconds...")
    print("       Watch for channel acquisition messages and errors...\n")

    # Need to run Qt event loop for acquisition worker to start!
    # Use QTimer to check progress
    elapsed = [0]
    def check_progress():
        elapsed[0] += 0.1
        if elapsed[0] >= 10:
            app.quit()

    progress_timer = QTimer()
    progress_timer.timeout.connect(check_progress)
    progress_timer.start(100)  # Check every 100ms

    app.exec()  # Run event loop

    print("\n[OK] Test complete - stopping acquisition")
    data_mgr.stop_acquisition()
    time.sleep(0.5)  # Let stop complete

    print("\n" + "=" * 70)
    print("TEST FINISHED SUCCESSFULLY")
    print("=" * 70)

except Exception as e:
    print(f"\n[FAIL] ACQUISITION FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    # Cleanup
    try:
        if hardware_mgr.ctrl:
            hardware_mgr.ctrl.close()
        if hardware_mgr.usb:
            hardware_mgr.usb.close()
    except:
        pass
