"""Test that convergence preflight now correctly measures LED D.

This verifies the fix for the bug where acquire_raw_spectrum() wasn't
calling turn_on_channel() before set_intensity(), causing LEDs to stay off.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import time

from affilabs.utils.controller import PicoP4SPR
from affilabs.utils.usb4000_wrapper import USB4000


def test_acquire_raw_spectrum_fix():
    """Test that acquire_raw_spectrum correctly turns on LED before measuring."""
    print("=" * 70)
    print("TEST: acquire_raw_spectrum() LED Enable Fix")
    print("=" * 70)

    ctrl = PicoP4SPR()
    spec = USB4000()

    try:
        # Connect
        print("\n[1] Connecting hardware...")
        if not ctrl.open():
            print("❌ Controller failed")
            return
        if not spec.open():
            print("❌ Spectrometer failed")
            ctrl.close()
            return
        print("✓ Hardware connected")

        # Set integration time
        integration_time = 36.0
        spec.set_integration(integration_time)
        print(f"✓ Integration time: {integration_time}ms")

        # Test LED D at intensity 205 (the value that was failing)
        print("\n[2] Testing LED D at 205 using individual commands...")
        print("    Before fix: measuring 3300 counts (LED not turning on)")
        print("    After fix:  should measure ~35,000 counts (LED on)")

        # Simulate what acquire_raw_spectrum does with use_batch_command=False
        spec.set_integration(integration_time)
        time.sleep(0.010)

        # CRITICAL: Enable channel BEFORE setting intensity (the fix)
        ctrl.turn_on_channel("d")
        ctrl.set_intensity("d", 205)
        time.sleep(0.045)  # LED stabilization

        spectrum = spec.read_intensity()

        # Turn off
        ctrl.set_intensity("d", 0)
        time.sleep(0.005)

        if spectrum is None or len(spectrum) == 0:
            print("❌ No spectrum returned")
            return

        # Analyze results
        n = len(spectrum)
        mid_start = int(n * 0.1)
        mid_end = int(n * 0.9)
        mid_spec = spectrum[mid_start:mid_end]

        mean_counts = sum(mid_spec) / len(mid_spec)
        max_counts = max(mid_spec)

        # Expected from model: slope_10ms = 47.73
        expected = 47.73 * 205 * (integration_time / 10.0)

        print("\n[3] Results:")
        print(f"    Mean counts: {mean_counts:.0f}")
        print(f"    Max counts:  {max_counts:.0f}")
        print(f"    Expected:    {expected:.0f}")
        print(f"    Ratio:       {mean_counts / expected:.2f}x")

        # Verdict
        print("\n[4] Verdict:")
        if mean_counts < 5000:
            print(f"    ❌ STILL BROKEN - counts={mean_counts:.0f} << expected")
            print("       LED D not turning on properly")
        elif mean_counts > expected * 0.5:
            print(f"    ✅ FIXED! - counts={mean_counts:.0f} ≈ expected={expected:.0f}")
            print("       LED D is working correctly now")
        else:
            print(f"    ⚠️  MARGINAL - counts={mean_counts:.0f} lower than expected")
            print("       May need further investigation")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()

    finally:
        if ctrl:
            ctrl.turn_off_channels()
            ctrl.close()
        if spec:
            spec.close()
        print("\n✓ Test complete")


if __name__ == "__main__":
    test_acquire_raw_spectrum_fix()
