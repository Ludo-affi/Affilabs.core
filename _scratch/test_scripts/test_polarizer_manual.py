"""Manual polarizer test - check if signal changes when polarizer rotates"""

import time
from affilabs.core.hardware_manager import HardwareManager

def test_manual_polarizer():
    """Test if manually rotating polarizer changes signal"""
    print("=" * 70)
    print("MANUAL POLARIZER TEST")
    print("=" * 70)
    print()
    print("This test will:")
    print("  1. Turn on LEDs at 20%")
    print("  2. Set detector integration time to 5ms")
    print("  3. Continuously display signal counts")
    print()
    print("INSTRUCTIONS:")
    print("  - Manually rotate the polarizer barrel by hand")
    print("  - Watch the signal counts change")
    print("  - If counts change significantly (3000 → 10000+), polarizer works!")
    print("  - If counts stay constant, check LED/detector alignment")
    print("  - Press Ctrl+C to stop")
    print("=" * 70)

    # Initialize hardware
    hm = HardwareManager()
    hm._connect_spectrometer()
    hm._connect_controller()

    if not hm.usb or not hm.ctrl:
        print("❌ Failed to connect to hardware")
        return

    print(f"✓ Connected to {hm.ctrl.__class__.__name__}")
    print(f"✓ Connected to detector: {hm.usb.get_serial()}")
    print()

    # Turn on LEDs at 20%
    print("Turning on LEDs at 20% (51/255)...")
    hm.ctrl.set_batch_intensities([51, 51, 51, 51])
    time.sleep(0.5)

    # Set integration time
    print("Setting integration time to 5ms...")
    hm.usb.set_integration(5.0)
    time.sleep(0.5)

    print()
    print("=" * 70)
    print("READING SIGNAL - Rotate polarizer barrel by hand!")
    print("=" * 70)
    print()

    try:
        while True:
            # Read spectrum
            spectrum = hm.usb.read_spectrum()
            max_intensity = max(spectrum)

            # Determine status
            if max_intensity > 10000:
                status = "BRIGHT (P or S window)"
            elif max_intensity > 3500:
                status = "MEDIUM"
            else:
                status = "DARK (between windows)"

            print(f"Signal: {max_intensity:7.1f} counts  [{status}]", end='\r')
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n")
        print("=" * 70)
        print("Test stopped by user")
        print("=" * 70)
    finally:
        # Turn off LEDs
        print("\nTurning off LEDs...")
        hm.ctrl.set_batch_intensities([0, 0, 0, 0])
        hm.cleanup()
        print("✓ Cleanup complete")

if __name__ == "__main__":
    test_manual_polarizer()
