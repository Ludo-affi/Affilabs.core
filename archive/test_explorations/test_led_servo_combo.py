"""Test LED + servo combo to diagnose blocking issue."""
import serial
import time

port_ctrl = 'COM3'  # P4PRO controller
baud = 115200

print("="*70)
print("LED + SERVO COMBO TEST")
print("="*70)

ser = serial.Serial(port_ctrl, baud, timeout=1)
time.sleep(0.5)
ser.read(1000)

print("\n1. Turn off LEDs (baseline)")
print("-" * 70)
ser.write(b"lx\n")
time.sleep(0.1)
ser.read(10)
print("LEDs OFF")

input("Check detector (should be ~3090). Press Enter...")

print("\n2. Move servo to PWM 128 (middle)")
print("-" * 70)
cmd = "servo:128,500\n"
print(f"Sending: {cmd!r}")
ser.write(cmd.encode())
time.sleep(1.2)  # 500ms move + 600ms settle
resp = ser.read(10)
print(f"Response: {resp!r}")

input("Servo moved to 128. Press Enter...")

print("\n3. Enable LEDs")
print("-" * 70)
ser.write(b"lm:ABCD\n")
time.sleep(0.1)
resp = ser.read(10)
print(f"lm:ABCD response: {resp!r}")

print("\n4. Set LED intensity to 20%")
print("-" * 70)
for ch in ['a', 'b', 'c', 'd']:
    cmd = f"l{ch}:51\n"
    ser.write(cmd.encode())
    time.sleep(0.01)
    ser.read(10)
print("Intensity set to 20% (51/255)")

print("\n** CHECK DETECTOR - Are LEDs visible now? **")
detector_reading = input("Enter detector reading (or 'low' if blocked): ")

if detector_reading.lower() == 'low' or (detector_reading.isdigit() and int(detector_reading) < 5000):
    print("\n⚠️  POLARIZER IS BLOCKING LIGHT at PWM 128")
    print("    Let's try different servo positions...")
    
    for test_pwm in [1, 65, 128, 191, 255]:
        print(f"\n5. Moving servo to PWM {test_pwm}")
        cmd = f"servo:{test_pwm},500\n"
        ser.write(cmd.encode())
        time.sleep(1.2)
        ser.read(10)
        reading = input(f"  Detector at PWM {test_pwm}: ")
        if reading.isdigit() and int(reading) > 10000:
            print(f"  ✓ FOUND TRANSMISSION WINDOW at PWM {test_pwm}!")

print("\n6. Turn off LEDs")
print("-" * 70)
ser.write(b"lx\n")
time.sleep(0.1)
ser.read(10)
print("LEDs OFF")

ser.close()
print("\n" + "="*70)
print("TEST COMPLETE")
print("="*70)
