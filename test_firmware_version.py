import serial
import time

# Check firmware version and test PWM bug
ser = serial.Serial('COM4', 115200, timeout=1)
time.sleep(0.2)

print("="*60)
print("FIRMWARE VERSION CHECK")
print("="*60)

# Check version
ser.write(b'iv\n')
time.sleep(0.1)
version = ser.read(100).decode().strip()
print(f"Firmware version: {version}")

ser.write(b'id\n')
time.sleep(0.1)
device = ser.read(100).decode().strip()
print(f"Device: {device}")

print("\n" + "="*60)
print("PWM BUG TEST")
print("="*60)

print("\nStep 1: Turn all LEDs OFF")
ser.write(b'lx\n')
time.sleep(0.3)
resp = ser.read(100)
print(f"Response: {resp}")
input(">>> Press ENTER after verifying ALL LEDs are OFF")

print("\nStep 2: Set LED A to 100% brightness and turn ON")
ser.write(b'ba255\n')
time.sleep(0.1)
resp = ser.read(100)
ser.write(b'la\n')
time.sleep(0.1)
resp = ser.read(100)
print(f"Response: {resp}")
input(">>> Press ENTER after verifying LED A is ON (bright)")

print("\nStep 3: Turn all LEDs OFF")
ser.write(b'lx\n')
time.sleep(0.3)
resp = ser.read(100)
print(f"Response: {resp}")

print("\n" + "="*60)
print("CRITICAL TEST: Look at the LEDs NOW")
print("="*60)
result = input("Is LED A still ON? (yes/no): ").strip().lower()

if result == 'yes':
    print("\n❌ PWM BUG EXISTS - LED latched ON at 100% brightness")
    print("   The lx command failed to turn off LED A")
    print("   This is the bug we need to fix")
else:
    print("\n✅ NO PWM BUG - LED turned OFF correctly!")
    print("   The sleep_ms(3) delay in the source code is working")
    print("   V1.2 firmware already has the fix!")

ser.close()
print("\nTest complete.")
