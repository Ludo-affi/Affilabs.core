"""Debug why channels A and D don't work with batch commands."""
import sys
import time
sys.path.insert(0, 'src')

from utils.controller import PicoP4SPR

def debug_channels():
    """Test each channel individually with detailed output."""
    print("Connecting to Pico...")
    pico = PicoP4SPR()

    if not pico.open():
        print("❌ Failed to connect")
        return

    print("✅ Connected\n")

    # Test each channel with batch command
    for ch_name, a, b, c, d in [
        ('A', 255, 0, 0, 0),
        ('B', 0, 255, 0, 0),
        ('C', 0, 0, 255, 0),
        ('D', 0, 0, 0, 255),
    ]:
        print("=" * 60)
        print(f"Testing LED {ch_name}")
        print("=" * 60)

        # Check if channel is already enabled
        print(f"Channel tracking state: {pico._channels_enabled}")

        # Send batch command
        print(f"Sending batch command: batch:{a},{b},{c},{d}")
        success = pico.set_batch_intensities(a=a, b=b, c=c, d=d)
        print(f"Command result: {'✅ SUCCESS' if success else '❌ FAILED'}")

        print(f">>> Watch LED {ch_name} - should be ON for 3 seconds <<<")
        time.sleep(3)

        # Turn off
        pico.set_batch_intensities(0, 0, 0, 0)
        print(f"LED {ch_name} turned OFF\n")
        time.sleep(1)

    # Now test with individual commands for comparison
    print("\n" + "=" * 60)
    print("COMPARISON: Individual commands on A and D")
    print("=" * 60)

    print("\nTesting LED A with individual command:")
    pico.set_intensity('a', 255)
    print(">>> LED A should be ON <<<")
    time.sleep(3)
    pico.set_intensity('a', 0)
    print("LED A OFF\n")

    time.sleep(1)

    print("Testing LED D with individual command:")
    pico.set_intensity('d', 255)
    print(">>> LED D should be ON <<<")
    time.sleep(3)
    pico.set_intensity('d', 0)
    print("LED D OFF\n")

    pico.close()
    print("Test complete!")

if __name__ == "__main__":
    debug_channels()
