"""Ultra-fast test to debug Start button crash - no UI, no calibration."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 70)
print("FAST START CRASH DEBUG TEST")
print("=" * 70)

# Minimal imports
from PySide6.QtWidgets import QApplication
from core.hardware_manager import HardwareManager
from core.data_acquisition_manager import DataAcquisitionManager
import time

print("\n[1/4] Creating Qt app...")
app = QApplication(sys.argv)

print("[2/4] Creating hardware manager...")
hardware_mgr = HardwareManager()

print("[3/4] Creating data acquisition manager...")
data_mgr = DataAcquisitionManager(hardware_mgr)

# Connect to hardware
print("\n[4/4] Connecting to hardware...")
scan_done = False

def on_connected(status):
    global scan_done
    print(f"   Hardware connected: {status}")
    scan_done = True

hardware_mgr.hardware_connected.connect(on_connected)
hardware_mgr.scan_and_connect()

# Process events until scan completes
timeout = 0
while not scan_done and timeout < 100:
    app.processEvents()
    time.sleep(0.05)
    timeout += 1

if not scan_done:
    print("[FAIL] Hardware scan timeout")
    sys.exit(1)

print(f"\n[OK] Hardware: ctrl={hardware_mgr.ctrl is not None}, usb={hardware_mgr.usb is not None}")

# Inject fake calibration (bypass real calibration)
print("\n[5/6] Injecting fake calibration data...")
import numpy as np
data_mgr.wave_data = np.array(range(200, 1100))  # 900 wavelengths as numpy
data_mgr.leds_calibrated = {'a': 255, 'b': 200, 'c': 180, 'd': 255}  # DICT not list!
data_mgr.ref_sig = {
    'a': np.ones(900) * 1000,
    'b': np.ones(900) * 1000,
    'c': np.ones(900) * 1000,
    'd': np.ones(900) * 1000
}
data_mgr.dark_noise = np.ones(900) * 100
data_mgr.integration_time = 40
data_mgr.num_scans = 5
data_mgr.calibrated = True
data_mgr.ref_intensity = 255
data_mgr.ch_error_list = []
print("[OK] Fake calibration complete")

# Now try to start acquisition (THIS is where it crashes)
print("\n[6/6] Starting acquisition (crash point)...")
print("=" * 70)

try:
    data_mgr.start_acquisition()
    print("\n[OK] start_acquisition() returned successfully")

    # Run event loop for 5 seconds to let worker start
    print("[TEST] Running event loop for 5 seconds...")
    print("       Watch for worker thread messages...\n")

    start_time = time.time()
    while time.time() - start_time < 5:
        app.processEvents()
        time.sleep(0.1)

    print("\n[OK] Test completed - stopping acquisition")
    data_mgr.stop_acquisition()
    time.sleep(0.5)

    print("\n" + "=" * 70)
    print("TEST PASSED - NO CRASH!")
    print("=" * 70)

except Exception as e:
    print(f"\n[FAIL] Exception during acquisition: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    # Cleanup
    if hardware_mgr.ctrl:
        hardware_mgr.ctrl.close()
    if hardware_mgr.usb:
        hardware_mgr.usb.close()

sys.exit(0)
