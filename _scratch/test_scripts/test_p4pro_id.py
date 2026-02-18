import serial
import time

print("Testing P4PRO firmware ID on COM3...")

s = serial.Serial('COM3', 115200, timeout=2)
time.sleep(0.5)
s.reset_input_buffer()

# Send ID command
s.write(b'id\n')
time.sleep(0.5)

# Read response
resp = s.readline().decode('utf-8', errors='ignore').strip()
s.close()

print(f"Firmware ID response: '{resp}'")
print(f"Contains 'P4PRO': {'P4PRO' in resp}")
print(f"Exact match 'P4PRO': {resp == 'P4PRO'}")
