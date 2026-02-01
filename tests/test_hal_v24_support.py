"""Test HAL V2.4 firmware support - batch and rank commands."""

from affilabs.utils.controller import PicoP4SPR
from affilabs.utils.hal.controller_hal import create_controller_hal
from affilabs.utils.device_configuration import DeviceConfiguration

def test_hal_v24_support():
    """Verify HAL supports V2.4 firmware features."""

    print("=" * 80)
    print("HAL V2.4 FIRMWARE SUPPORT TEST")
    print("=" * 80)

    # Create raw controller
    print("\n1. Creating PicoP4SPR controller...")
    ctrl_raw = PicoP4SPR()

    if not ctrl_raw.open():
        print("❌ Failed to connect to PicoP4SPR")
        return False

    print(f"✓ Connected: {ctrl_raw.version}")

    # Wrap with HAL
    print("\n2. Wrapping with HAL...")
    device_config = DeviceConfiguration()
    ctrl = create_controller_hal(ctrl_raw, device_config)
    print("✓ HAL wrapper created")

    # Test capability flags
    print("\n3. Checking V2.4 capability flags...")
    print(f"   - supports_batch_leds: {ctrl.supports_batch_leds}")
    print(f"   - supports_rank_sequence: {ctrl.supports_rank_sequence}")

    if not ctrl.supports_batch_leds:
        print("❌ HAL missing batch LED support!")
        return False

    if not ctrl.supports_rank_sequence:
        print("❌ HAL missing rank sequence support!")
        return False

    print("✓ Both capabilities supported")

    # Test batch command
    print("\n4. Testing batch command...")
    try:
        success = ctrl.set_batch_intensities(a=50, b=50, c=50, d=50)
        if success:
            print("✓ Batch command executed")
        else:
            print("⚠ Batch command returned False")
    except Exception as e:
        print(f"❌ Batch command error: {e}")
        return False
    finally:
        ctrl.turn_off_channels()

    # Test rank sequence (just check it's callable)
    print("\n5. Testing rank sequence interface...")
    try:
        # Don't actually run the sequence, just verify it's callable
        rank_gen = ctrl.led_rank_sequence(test_intensity=100, settling_ms=45, dark_ms=5)
        if rank_gen is not None:
            print("✓ Rank sequence generator created")
            # Close the generator without iterating
            try:
                rank_gen.close()
            except:
                pass
        else:
            print("❌ Rank sequence returned None")
            return False
    except Exception as e:
        print(f"❌ Rank sequence error: {e}")
        return False

    # Cleanup
    print("\n6. Cleanup...")
    ctrl.turn_off_channels()
    ctrl.close()
    print("✓ Controller closed")

    print("\n" + "=" * 80)
    print("✓ ALL V2.4 FEATURES SUPPORTED IN HAL")
    print("=" * 80)
    return True


if __name__ == "__main__":
    import sys
    success = test_hal_v24_support()
    sys.exit(0 if success else 1)
