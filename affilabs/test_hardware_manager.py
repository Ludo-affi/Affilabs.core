"""Full diagnostic test - mimics what main_simplified does."""
import sys
sys.path.insert(0, r'c:\Users\ludol\ezControl-AI\Affilabs.core beta')

from core.hardware_manager import HardwareManager
from affilabs.utils.logger import logger
import threading
import time

print("="*60)
print("FULL HARDWARE MANAGER TEST")
print("="*60)

# Create hardware manager
hw_mgr = HardwareManager()

# Connect to hardware_connected signal
def on_connected(status):
    print("\n" + "="*60)
    print("[OK] HARDWARE CONNECTED CALLBACK!")
    print(f"   Status: {status}")
    print("="*60 + "\n")

hw_mgr.hardware_connected.connect(on_connected)

# Start scan (like main_simplified does)
print("\nStarting hardware scan...")
hw_mgr.scan_and_connect()

# Wait for connection to complete
print("Waiting for connection thread to finish...")
time.sleep(5)

print("\n" + "="*60)
print("FINAL RESULTS:")
print(f"  ctrl: {hw_mgr.ctrl}")
print(f"  knx: {hw_mgr.knx}")
print(f"  pump: {hw_mgr.pump}")
print(f"  usb: {hw_mgr.usb}")
print("="*60)
