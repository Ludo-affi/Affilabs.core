"""
Simple test - do basic LED commands still work?
"""

import serial
import time

print("Testing basic LED commands after firmware changes...\n")

ser = serial.Serial('COM5', 115200, timeout=1)
time.sleep(0.5)

# Test LED A
print("1. Setting LED A brightness to 128...")
ser.write(b'ba128\n')
time.sleep(0.1)
ack = ser.read(1)
print(f"   ACK: {ack}")

print("2. Turning ON LED A...")
ser.write(b'la\n')
time.sleep(0.1)
ack = ser.read(1)
print(f"   ACK: {ack}")
print("   >>> Is LED A ON? (wait 3 seconds)")
time.sleep(3)

print("3. Turning OFF all LEDs...")
ser.write(b'lx\n')
time.sleep(0.1)
ack = ser.read(1)
print(f"   ACK: {ack}")
print("   >>> Are all LEDs OFF?")
time.sleep(2)

# Test LED C
print("4. Setting LED C brightness to 128...")
ser.write(b'bc128\n')
time.sleep(0.1)
ack = ser.read(1)
print(f"   ACK: {ack}")

print("5. Turning ON LED C...")
ser.write(b'lc\n')
time.sleep(0.1)
ack = ser.read(1)
print(f"   ACK: {ack}")
print("   >>> Is LED C ON? (wait 3 seconds)")
time.sleep(3)

print("6. Turning OFF all LEDs...")
ser.write(b'lx\n')
time.sleep(0.1)
ack = ser.read(1)
print(f"   ACK: {ack}")
print("   >>> Are all LEDs OFF?")

ser.close()

print("\n" + "="*60)
print("Results:")
print("  • Did LED A turn on in step 2?")
print("  • Did all LEDs turn off in step 3?")
print("  • Did LED C turn on in step 5?")
print("  • Did all LEDs turn off in step 6?")
print("="*60)
