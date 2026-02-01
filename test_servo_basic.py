"""Test basic servo PWM commands - the old working format."""

import time
import serial

ser = serial.Serial('COM4', 115200, timeout=1)

print("Testing basic servo commands that were working...\n")

# Enable servo power
print("1. Enable servo power")
ser.write(b"sp1\n")
time.sleep(0.1)
resp = ser.read(10)
print(f"   sp1 response: {resp!r}")
print("   (Servo should be powered on now)")
time.sleep(0.5)

# Test the old sv{s_pwm}{p_pwm} format with PWM values
print("\n2. Test sv{s_pwm}{p_pwm} format - BOTH positions at once")
positions = [
    (10, 100),   # S=10, P=100
    (50, 150),   # S=50, P=150
    (100, 200),  # S=100, P=200
    (133, 35),   # Your actual device config values
]

for s_pwm, p_pwm in positions:
    cmd = f"sv{s_pwm:03d}{p_pwm:03d}\n"
    print(f"\n   Sending: {cmd.strip()} (S={s_pwm}, P={p_pwm})")
    ser.reset_input_buffer()
    ser.write(cmd.encode())
    time.sleep(0.05)
    resp = ser.read(10)
    print(f"   Response: {resp!r}")
    time.sleep(1.0)
    input("   >>> Did servo MOVE? Press Enter to continue...")

# Test single servo command if it exists
print("\n3. Test if there's a single-servo command")
single_commands = [
    "ss090\n",  # set servo to 90
    "s090\n",   # servo 90
]

for cmd in single_commands:
    print(f"\n   Trying: {cmd.strip()}")
    ser.reset_input_buffer()
    ser.write(cmd.encode())
    time.sleep(0.05)
    resp = ser.read(10)
    print(f"   Response: {resp!r}")
    time.sleep(0.5)

ser.close()
print("\n✅ Done!")
