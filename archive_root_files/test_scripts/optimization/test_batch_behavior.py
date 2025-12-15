"""Test if batch command keeps LEDs on or turns them off."""

import sys
import time

sys.path.insert(0, "src")

from utils.controller import PicoP4SPR


def test_batch_behavior():
    """Test batch command behavior."""
    print("Connecting to Pico...")
    pico = PicoP4SPR()

    if not pico.open():
        print("❌ Failed to connect")
        return

    print("✅ Connected\n")

    # First enable and set all channels individually
    print("Step 1: Enable and light all 4 LEDs individually")
    for ch in ["a", "b", "c", "d"]:
        pico._ser.reset_input_buffer()
        pico._ser.write(f"l{ch}\n".encode())
        time.sleep(0.02)
        pico._ser.read(10)

        pico._ser.reset_input_buffer()
        pico._ser.write(f"b{ch}255\n".encode())
        time.sleep(0.02)
        pico._ser.read(10)

    print(">>> ALL 4 LEDs should be ON now <<<")
    time.sleep(3)

    # Now send batch command to turn on only A
    print("\nStep 2: Send batch command batch:255,0,0,0 (only A should stay on)")
    pico._ser.reset_input_buffer()
    pico._ser.write(b"batch:255,0,0,0\n")
    time.sleep(0.05)
    response = pico._ser.read(10)
    print(f"Batch response: {response!r}")

    print(">>> Only LED A should be ON, B/C/D should be OFF <<<")
    time.sleep(3)

    # Try another batch pattern
    print("\nStep 3: Send batch command batch:0,255,255,0 (only B and C)")
    pico._ser.reset_input_buffer()
    pico._ser.write(b"batch:0,255,255,0\n")
    time.sleep(0.05)
    response = pico._ser.read(10)
    print(f"Batch response: {response!r}")

    print(">>> Only LEDs B and C should be ON <<<")
    time.sleep(3)

    # Turn all off
    print("\nStep 4: Turn all off with batch:0,0,0,0")
    pico._ser.write(b"batch:0,0,0,0\n")
    time.sleep(0.1)
    print("All LEDs should be OFF")

    pico.close()
    print("\nTest complete!")


if __name__ == "__main__":
    test_batch_behavior()
