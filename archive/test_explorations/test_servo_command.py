"""Test P4PRO servo commands to find which format works."""
import logging
import sys
from affilabs.core.hardware_manager import HardwareManager

# Fix Unicode encoding for Windows terminal
sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize hardware
import time
hm = HardwareManager()
print("Scanning for hardware...")
result = hm.scan_and_connect(auto_connect=True)
print(f"Scan result: {result}")
time.sleep(2)  # Wait for connection
ctrl_adapter = hm.ctrl

if ctrl_adapter is None:
    print("❌ No controller found!")
    exit(1)

# Get the actual PicoP4PRO controller object
ctrl = ctrl_adapter._controller
port = ctrl._port

print(f"\n{'='*60}")
print(f"P4PRO Controller found on {port}")
print(f"Device type: {ctrl_adapter.get_device_type()}")
print(f"{'='*60}\n")

# Test different servo command formats
import serial
import time

ser = serial.Serial(port, 115200, timeout=1)

print("\n🧪 TEST 1: servo:ANGLE,DURATION format (PicoEZSPR style)")
print("   Command: servo:45,150")
ser.reset_input_buffer()
ser.write(b"servo:45,150\n")
time.sleep(0.5)
resp = ser.read(20)
print(f"   Response: {resp!r}")
ack1 = b'1' in resp or b'\x01' in resp
print(f"   Result: {'✅ ACK' if ack1 else '❌ No response'}")

time.sleep(2)

print("\n🧪 TEST 2: sv{PWM}{PWM} format (current PicoP4PRO style)")
print("   Command: sv090090")
ser.reset_input_buffer()
ser.write(b"sv090090\n")
time.sleep(0.5)
resp = ser.read(20)
print(f"   Response: {resp!r}")
ack2 = b'1' in resp or b'\x01' in resp
print(f"   Result: {'✅ ACK' if ack2 else '❌ No response'}")

time.sleep(2)

print("\n🧪 TEST 3: ss/sp commands (old style)")
print("   Command: ss")
ser.reset_input_buffer()
ser.write(b"ss\n")
time.sleep(0.5)
resp = ser.read(20)
print(f"   Response: {resp!r}")
ack3 = b'1' in resp or b'\x01' in resp
print(f"   Result: {'✅ ACK' if ack3 else '❌ No response'}")

ser.close()

print(f"\n{'='*60}")
print("✅ Test complete - check which command format got ACK")
print(f"{'='*60}\n")

# Close hardware
hm.shutdown()
