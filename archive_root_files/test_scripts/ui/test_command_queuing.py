"""Test if we can send multiple LED commands without waiting for response."""
import sys
import time
sys.path.insert(0, 'src')

from utils.controller import PicoP4SPR

def test_command_queuing():
    """Test rapid command sending without waiting for responses."""
    print("Connecting to Pico...")
    pico = PicoP4SPR()

    if not pico.open():
        print("❌ Failed to connect")
        return

    print("✅ Connected\n")

    # Test 1: Send 4 LED commands as fast as possible (no waiting)
    print("=" * 60)
    print("TEST 1: Send 4 LED ON commands rapidly (no response wait)")
    print("=" * 60)

    channels = ['a', 'b', 'c', 'd']
    start = time.time()

    for ch in channels:
        cmd = f"l{ch}\n"  # Enable channel
        pico._ser.write(cmd.encode())
        cmd = f"w{ch}255\n"  # Set intensity
        pico._ser.write(cmd.encode())

    elapsed_ms = (time.time() - start) * 1000
    print(f"Sent 8 commands in {elapsed_ms:.2f}ms")
    print(">>> Watch your LEDs - should all be ON <<<")
    time.sleep(3)

    # Turn all off
    for ch in channels:
        pico._ser.write(f"w{ch}0\n".encode())

    print("\n" + "=" * 60)
    print("TEST 2: Send commands with small delays")
    print("=" * 60)

    time.sleep(1)
    start = time.time()

    for ch in channels:
        pico._ser.write(f"l{ch}\n".encode())
        time.sleep(0.005)  # 5ms delay
        pico._ser.write(f"w{ch}255\n".encode())
        time.sleep(0.005)

    elapsed_ms = (time.time() - start) * 1000
    print(f"Sent 8 commands in {elapsed_ms:.2f}ms (with 5ms delays)")
    print(">>> Watch your LEDs - should all be ON <<<")
    time.sleep(3)

    # Turn all off
    for ch in channels:
        pico._ser.write(f"w{ch}0\n".encode())

    print("\nTest complete!")
    pico.close()

if __name__ == "__main__":
    test_command_queuing()
