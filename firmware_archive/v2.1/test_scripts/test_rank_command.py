"""Test if V1.9 firmware supports 'rank' command for automatic LED sequencing"""

import sys

from affilabs.utils.controller import PicoP4SPR


def test_rank_command():
    """Test if rank command is available in current firmware"""
    print("\n" + "=" * 70)
    print("TESTING FIRMWARE 'rank' COMMAND")
    print("=" * 70)

    try:
        # Initialize controller
        ctrl = PicoP4SPR()
        if not ctrl.open():
            print("❌ Failed to connect to controller")
            return False

        print("✅ Controller connected")

        # Test if method exists
        if not hasattr(ctrl, "led_rank_sequence"):
            print("❌ led_rank_sequence() method not found")
            return False

        print("✅ led_rank_sequence() method exists")

        # Try to execute rank command (will timeout if firmware doesn't support it)
        print("\nSending rank command: rank:100,35,5")
        print("(intensity=100, settle=35ms, dark=5ms)")
        print("\nIf firmware supports it, you'll see:")
        print("  START")
        print("  a:READY → a:READ → a:DONE")
        print("  b:READY → b:READ → b:DONE")
        print("  ... etc")
        print("\nIf firmware DOESN'T support it, this will timeout in 5 seconds...")
        print("-" * 70)

        try:
            for ch, signal in ctrl.led_rank_sequence(
                test_intensity=100,
                settling_ms=35,
                dark_ms=5,
                timeout_s=5.0,
            ):
                print(f"  {ch.upper()}: {signal}")

            print("\n✅ SUCCESS! Rank command is SUPPORTED in your V1.9 firmware!")
            print("\nThis means we can eliminate Python timing overhead by using")
            print("firmware-controlled LED sequencing. Expected speedup:")
            print("  Current: ~367ms per channel")
            print("  With rank: ~280ms per channel (23% faster!)")
            return True

        except TimeoutError:
            print("\n⚠️  TIMEOUT: Rank command not supported in firmware")
            print("V1.9 firmware doesn't have this feature yet.")
            print("\nWe'll need to optimize Python-side timing instead:")
            print("  1. Remove excessive logging (biggest win)")
            print("  2. Skip LED OFF command (use pre-loading)")
            return False

        except Exception as e:
            print(f"\n❌ ERROR testing rank command: {e}")
            return False

    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

    finally:
        if "ctrl" in locals():
            ctrl.close()
            print("\nController disconnected")


if __name__ == "__main__":
    result = test_rank_command()
    sys.exit(0 if result else 1)
