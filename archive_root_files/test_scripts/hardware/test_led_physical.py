"""Test if LEDs physically light even if query says 0."""

import sys
import time

sys.path.insert(0, "src")

from utils.controller import PicoP4SPR


def test_led_physical():
    """Test if LEDs physically light."""
    print("Connecting to Pico...")
    pico = PicoP4SPR()

    if not pico.open():
        print("❌ Failed to connect")
        return

    print("✅ Connected\n")

    print("=" * 60)
    print("Testing LED A - Individual command")
    print("=" * 60)
    print("Sending: la (enable), ba255 (set intensity)")
    pico._ser.reset_input_buffer()
    pico._ser.write(b"la\n")
    time.sleep(0.05)
    print(f"Enable response: {pico._ser.read(10)!r}")

    pico._ser.reset_input_buffer()
    pico._ser.write(b"ba255\n")
    time.sleep(0.05)
    print(f"Intensity response: {pico._ser.read(10)!r}")

    print("\n>>> LOOK AT LED A - IS IT LIT? <<<")
    print("Waiting 5 seconds...")
    time.sleep(5)

    # Query state
    pico._ser.reset_input_buffer()
    pico._ser.write(b"ia\n")
    time.sleep(0.05)
    print(f"\nQuery LED A state: {pico._ser.read(10)!r}")

    # Turn off
    pico._ser.write(b"ba000\n")
    time.sleep(0.1)
    print("LED A turned OFF\n")

    time.sleep(1)

    print("=" * 60)
    print("Testing LED D - Individual command")
    print("=" * 60)
    print("Sending: ld (enable), bd255 (set intensity)")
    pico._ser.reset_input_buffer()
    pico._ser.write(b"ld\n")
    time.sleep(0.05)
    print(f"Enable response: {pico._ser.read(10)!r}")

    pico._ser.reset_input_buffer()
    pico._ser.write(b"bd255\n")
    time.sleep(0.05)
    print(f"Intensity response: {pico._ser.read(10)!r}")

    print("\n>>> LOOK AT LED D - IS IT LIT? <<<")
    print("Waiting 5 seconds...")
    time.sleep(5)

    # Query state
    pico._ser.reset_input_buffer()
    pico._ser.write(b"id\n")
    time.sleep(0.05)
    print(f"\nQuery LED D state: {pico._ser.read(10)!r}")

    # Turn off
    pico._ser.write(b"bd000\n")
    time.sleep(0.1)
    print("LED D turned OFF\n")

    pico.close()
    print("Test complete!")


if __name__ == "__main__":
    test_led_physical()
