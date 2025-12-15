"""Test LED D directly to verify it works."""

import sys
import time
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from affilabs.utils.controller import PicoP4SPR
from affilabs.utils.usb4000_wrapper import USB4000


def test_led_d():
    """Test LED D at different intensities."""
    ctrl = PicoP4SPR()
    spec = None

    try:
        print("=" * 70)
        print("LED D HARDWARE TEST")
        print("=" * 70)

        # Connect controller
        print("\n[1] Connecting to controller...")
        if not ctrl.open():
            print("❌ Failed to open controller")
            return
        print("✓ Controller connected")

        # Connect spectrometer
        print("\n[2] Connecting to spectrometer...")
        spec = USB4000()
        if not spec.open():
            print("❌ Failed to connect spectrometer")
            return
        print(f"✓ Spectrometer connected: {spec.serial_number}")

        # Set integration time
        integration_time = 36.0
        spec.set_integration(integration_time)
        print(f"✓ Integration time: {integration_time}ms")

        print("\n[3] Testing LED D:")
        print(f"    Expected model: counts = 47.73 × LED × ({integration_time}/10)")
        print()

        for led_val in [50, 100, 150, 200, 255]:
            # Turn on D
            ctrl.turn_on_channel("d")
            ctrl.set_intensity("d", led_val)
            time.sleep(0.15)

            # Measure
            spectrum = spec.read_intensity()
            if spectrum is not None and len(spectrum) > 0:
                n = len(spectrum)
                mid_start = int(n * 0.1)
                mid_end = int(n * 0.9)
                mid_spec = spectrum[mid_start:mid_end]

                max_counts = max(mid_spec)
                mean_counts = sum(mid_spec) / len(mid_spec)

                # Expected from model
                expected = 47.73 * led_val * (integration_time / 10.0)

                status = "✓" if mean_counts > expected * 0.5 else "❌"
                print(
                    f"  LED={led_val:3d}: mean={mean_counts:7.0f}  max={max_counts:7.0f}  expect={expected:7.0f}  {status}",
                )
            else:
                print(f"  LED={led_val:3d}: ❌ No data")

            # Turn off
            ctrl.turn_off_channels()
            time.sleep(0.05)

        print("\n[4] Verdict:")
        print("    If mean >> expected × 0.5 → LED D WORKS")
        print("    If mean << expected × 0.5 → LED D BROKEN or wrong channel")

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
    test_led_d()
