"""Test raw servo commands to understand V2.4 firmware."""

import time
import serial

def test_servo():
    ser = serial.Serial('COM4', 115200, timeout=1)

    print("Testing different servo command formats...\n")

    # Test 1: Check if servo needs enabling
    print("="*60)
    print("Test 1: Checking servo enable/power commands")
    print("="*60)

    possible_enable_commands = [
        "se\n",      # servo enable
        "sp1\n",     # servo power on
        "se1\n",     # servo enable 1
    ]

    for cmd in possible_enable_commands:
        print(f"\n📤 Trying: {cmd.strip()}")
        ser.reset_input_buffer()
        ser.write(cmd.encode())
        time.sleep(0.1)
        resp = ser.read(100)
        print(f"📥 Response: {resp!r}")

    # Test 2: Old dual-servo format
    print("\n" + "="*60)
    print("Test 2: Old sv{s}{p} dual-servo format")
    print("="*60)

    # sv{s_pwm:03d}{p_pwm:03d}\n
    cmd = "sv090090\n"  # Both servos to 90
    print(f"\n📤 Sending: {cmd.strip()}")
    ser.reset_input_buffer()
    ser.write(cmd.encode())
    time.sleep(0.1)
    resp = ser.read(100)
    print(f"📥 Response: {resp!r}")
    time.sleep(1.0)
    print("   (Check if servo moved)")

    # Test 3: New servo:ANGLE,DURATION format
    print("\n" + "="*60)
    print("Test 3: New servo:ANGLE,DURATION format")
    print("="*60)

    cmd = "servo:90,500\n"
    print(f"\n📤 Sending: {cmd.strip()}")
    ser.reset_input_buffer()
    ser.write(cmd.encode())
    time.sleep(0.1)
    resp = ser.read(100)
    print(f"📥 Response: {resp!r}")
    time.sleep(1.0)
    print("   (Check if servo moved)")

    # Test 4: Try alternative new format
    print("\n" + "="*60)
    print("Test 4: Alternative formats")
    print("="*60)

    alternatives = [
        "sm90\n",          # servo move 90
        "sa90\n",          # servo angle 90
        "servo 90\n",      # servo with space
        "servo:90\n",      # servo without duration
    ]

    for cmd in alternatives:
        print(f"\n📤 Trying: {cmd.strip()}")
        ser.reset_input_buffer()
        ser.write(cmd.encode())
        time.sleep(0.1)
        resp = ser.read(100)
        print(f"📥 Response: {resp!r}")
        time.sleep(0.5)

    # Test 5: Get help from firmware
    print("\n" + "="*60)
    print("Test 5: Firmware help/command list")
    print("="*60)

    help_commands = ["help\n", "?\n", "h\n", "commands\n"]

    for cmd in help_commands:
        print(f"\n📤 Trying: {cmd.strip()}")
        ser.reset_input_buffer()
        ser.write(cmd.encode())
        time.sleep(0.2)
        resp = ser.read(1000)
        if resp:
            print(f"📥 Response:\n{resp.decode('utf-8', errors='ignore')}")

    ser.close()
    print("\n✅ Test complete!")

if __name__ == "__main__":
    test_servo()
