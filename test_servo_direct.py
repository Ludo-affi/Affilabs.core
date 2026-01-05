"""Test P4PRO servo commands directly - bypass HardwareManager."""
import serial
import time
import sys

# Fix Unicode encoding
sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None

# Find P4PRO controller
from affilabs.utils import controller

print("\n" + "="*60)
print("Scanning for P4PRO controller...")
print("="*60 + "\n")

ports_to_test = ['COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8']
p4pro_port = None

for port in ports_to_test:
    try:
        print(f"Trying {port}...", end=" ")
        ser = serial.Serial(port, 115200, timeout=0.5)
        ser.write(b"v\n")  # Version command
        time.sleep(0.1)
        resp = ser.read(100).decode('utf-8', errors='ignore')
        ser.close()
        
        if "P4PRO" in resp:
            print(f"FOUND! Response: {resp.strip()}")
            p4pro_port = port
            break
        else:
            print(f"Not P4PRO (got: {resp.strip()[:30]})")
    except:
        print("Not available")

if not p4pro_port:
    print("\n[X] P4PRO not found on any COM port!")
    exit(1)

print(f"\n{'='*60}")
print(f"P4PRO found on {p4pro_port}")
print(f"{'='*60}\n")

# Test servo commands
ser = serial.Serial(p4pro_port, 115200, timeout=1)

print("\nTEST 1: servo:ANGLE,DURATION format (PicoEZSPR style)")
print("   Command: servo:45,150\\n")
ser.reset_input_buffer()
ser.write(b"servo:45,150\n")
time.sleep(0.5)
resp = ser.read(20)
print(f"   Response: {resp!r}")
ack1 = b'1' in resp or b'\x01' in resp
print(f"   Result: {'ACK RECEIVED' if ack1 else 'NO RESPONSE'}")

time.sleep(2)

print("\nTEST 2: sv{PWM}{PWM} format (current PicoP4PRO style)")
print("   Command: sv090090\\n")
ser.reset_input_buffer()
ser.write(b"sv090090\n")
time.sleep(0.5)
resp = ser.read(20)
print(f"   Response: {resp!r}")
ack2 = b'1' in resp or b'\x01' in resp
print(f"   Result: {'ACK RECEIVED' if ack2 else 'NO RESPONSE'}")

time.sleep(2)

print("\nTEST 3: ss/sp commands (old style)")
print("   Command: ss\\n")
ser.reset_input_buffer()
ser.write(b"ss\n")
time.sleep(0.5)
resp = ser.read(20)
print(f"   Response: {resp!r}")
ack3 = b'1' in resp or b'\x01' in resp
print(f"   Result: {'ACK RECEIVED' if ack3 else 'NO RESPONSE'}")

ser.close()

print(f"\n{'='*60}")
print("Test complete!")
if ack1:
    print("USE: servo:ANGLE,DURATION format")
elif ack2:
    print("USE: sv{PWM}{PWM} format")
elif ack3:
    print("USE: ss/sp commands")
else:
    print("NONE of the servo commands responded!")
print(f"{'='*60}\n")
