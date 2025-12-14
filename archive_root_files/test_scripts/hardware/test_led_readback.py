"""Test LED control with state readback verification."""
import sys
import time
sys.path.insert(0, 'src')

from utils.controller import PicoP4SPR

def test_led_with_readback():
    """Test LED commands and verify state readback."""
    print("Connecting to Pico...")
    pico = PicoP4SPR()

    if not pico.open():
        print("❌ Failed to connect to Pico")
        return

    print(f"✅ Connected to Pico controller")
    print()

    # Test sequence
    channels = [
        ('A', 255, 0, 0, 0),
        ('B', 0, 255, 0, 0),
        ('C', 0, 0, 255, 0),
        ('D', 0, 0, 0, 255),
    ]

    for ch_name, a, b, c, d in channels:
        print(f"🔆 Testing LED {ch_name}")
        print(f"   Sending batch command: batch:{a},{b},{c},{d}")

        # Send batch command
        success = pico.set_batch_intensities(a=a, b=b, c=c, d=d)
        print(f"   Command result: {'✅ SUCCESS' if success else '❌ FAILED'}")

        # Read back LED states
        time.sleep(0.1)  # Wait for command to take effect

        # Query each LED state
        for query_ch in ['a', 'b', 'c', 'd']:
            try:
                pico._ser.write(f"i{query_ch}\n".encode())
                time.sleep(0.02)
                response = pico._ser.read(50)
                print(f"   LED {query_ch.upper()} state: {response}")
            except Exception as e:
                print(f"   LED {query_ch.upper()} query failed: {e}")

        print()
        time.sleep(1)

        # Turn off
        pico.set_batch_intensities(0, 0, 0, 0)
        time.sleep(0.5)

    print("Test complete!")
    pico.close()

if __name__ == "__main__":
    test_led_with_readback()
