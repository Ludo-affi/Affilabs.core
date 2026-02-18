"""
Quick test to verify P4PRO LED batch control is working correctly.
Tests the fixed set_batch_intensities() approach for live data acquisition.
"""
import time
import sys
from affilabs.utils.controller import PicoP4PRO

def test_p4pro_led_batch():
    """Test P4PRO LED control using set_batch_intensities() approach."""
    print("=" * 80)
    print("P4PRO LED BATCH CONTROL TEST")
    print("=" * 80)

    # Initialize controller
    ctrl = PicoP4PRO()

    if not ctrl.open():
        print("❌ FAILED: Could not connect to P4PRO")
        return False

    print("✅ Connected to P4PRO")
    print()

    # Test intensities (matching calibration values)
    test_intensities = {
        'a': 177,
        'b': 148,
        'c': 71,
        'd': 61
    }

    channels = ['a', 'b', 'c', 'd']

    print("Cycling through channels (like live data):")
    print("Press Ctrl+C to stop...")
    print("-" * 80)

    all_success = True
    cycle_count = 0

    try:
        while True:
            cycle_count += 1
            print(f"\n🔄 CYCLE {cycle_count}")

            for ch in channels:
                # Set batch with ONLY this channel enabled (same as fixed code)
                start_time = time.perf_counter()

                success = ctrl.set_batch_intensities(
                    a=test_intensities['a'] if ch == 'a' else 0,
                    b=test_intensities['b'] if ch == 'b' else 0,
                    c=test_intensities['c'] if ch == 'c' else 0,
                    d=test_intensities['d'] if ch == 'd' else 0
                )

                elapsed_ms = (time.perf_counter() - start_time) * 1000

                if success:
                    print(f"  ✅ Ch {ch.upper()}: LED ON ({elapsed_ms:.1f}ms, intensity={test_intensities[ch]})")
                else:
                    print(f"  ❌ Ch {ch.upper()}: FAILED")
                    all_success = False

                # Wait like real acquisition (detector stabilization + read)
                time.sleep(0.045)  # 45ms detector wait
                time.sleep(0.05)   # Simulate spectrum read

    except KeyboardInterrupt:
        print(f"\n\n⏹️  Stopped after {cycle_count} cycles")
        pass

    print("\n" + "=" * 80)

    # Turn off all LEDs
    print("\nTurning off all LEDs...")
    ctrl.set_batch_intensities(a=0, b=0, c=0, d=0)
    time.sleep(0.1)

    if all_success:
        print("✅ ALL TESTS PASSED - Live data LED control should work!")
    else:
        print("❌ SOME TESTS FAILED - Check P4PRO firmware and connections")

    print("=" * 80)

    return all_success


if __name__ == "__main__":
    try:
        success = test_p4pro_led_batch()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ TEST CRASHED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
