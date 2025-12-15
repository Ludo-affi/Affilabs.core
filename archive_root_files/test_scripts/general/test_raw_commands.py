"""Test the actual commands being sent."""

import sys
import time

sys.path.insert(0, "src")

from utils.controller import PicoP4SPR


def test_raw_commands():
    """Send raw commands and see responses."""
    print("Connecting to Pico...")
    pico = PicoP4SPR()

    if not pico.open():
        print("❌ Failed to connect")
        return

    print("✅ Connected\n")

    # Test different command formats
    tests = [
        ("Enable channel A", "la\n"),
        ("Set LED A intensity (b format)", "ba255\n"),
        ("Check LED A state", "ia\n"),
        ("Enable channel D", "ld\n"),
        ("Set LED D intensity (b format)", "bd255\n"),
        ("Check LED D state", "id\n"),
    ]

    for desc, cmd in tests:
        print(f"\n{desc}: {cmd!r}")
        pico._ser.reset_input_buffer()
        pico._ser.write(cmd.encode())
        time.sleep(0.05)
        response = pico._ser.read(20)
        print(f"  Response: {response!r}")
        time.sleep(0.5)

    print("\n>>> Check if LEDs A or D are lit <<<")
    time.sleep(3)

    # Turn off
    print("\nTurning off all channels: lx")
    pico._ser.write(b"lx\n")
    time.sleep(0.05)
    response = pico._ser.read(20)
    print(f"  Response: {response!r}")

    pico.close()
    print("\nTest complete!")


if __name__ == "__main__":
    test_raw_commands()
