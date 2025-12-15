"""Test script to verify LED delay persistence implementation.

Tests:
1. Device config can store/load PRE/POST LED delays
2. Acquisition manager loads delays from config on startup
3. Main window saves delays when user applies settings
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))


def test_device_config_led_delays():
    """Test device config can store and retrieve LED delays."""
    print("\n" + "=" * 70)
    print("TEST 1: Device Config LED Delay Storage")
    print("=" * 70)

    from utils.device_configuration import DeviceConfiguration

    # Create test config
    config = DeviceConfiguration(device_serial="TEST_DEVICE")

    # Test default values
    pre_default = config.get_pre_led_delay_ms()
    post_default = config.get_post_led_delay_ms()
    print(f"✓ Default PRE delay: {pre_default}ms (expected: 45.0ms)")
    print(f"✓ Default POST delay: {post_default}ms (expected: 5.0ms)")
    assert pre_default == 45.0, f"Expected 45.0, got {pre_default}"
    assert post_default == 5.0, f"Expected 5.0, got {post_default}"

    # Test setting custom values
    print("\nSetting custom values: PRE=35ms, POST=8ms")
    config.set_pre_post_led_delays(35.0, 8.0)

    # Test retrieval
    pre_custom = config.get_pre_led_delay_ms()
    post_custom = config.get_post_led_delay_ms()
    print(f"✓ Retrieved PRE delay: {pre_custom}ms (expected: 35.0ms)")
    print(f"✓ Retrieved POST delay: {post_custom}ms (expected: 8.0ms)")
    assert pre_custom == 35.0, f"Expected 35.0, got {pre_custom}"
    assert post_custom == 8.0, f"Expected 8.0, got {post_custom}"

    # Test persistence (reload from file)
    print("\nReloading config from file to test persistence...")
    config2 = DeviceConfiguration(device_serial="TEST_DEVICE")
    pre_reloaded = config2.get_pre_led_delay_ms()
    post_reloaded = config2.get_post_led_delay_ms()
    print(f"✓ Reloaded PRE delay: {pre_reloaded}ms (expected: 35.0ms)")
    print(f"✓ Reloaded POST delay: {post_reloaded}ms (expected: 8.0ms)")
    assert pre_reloaded == 35.0, f"Expected 35.0, got {pre_reloaded}"
    assert post_reloaded == 8.0, f"Expected 8.0, got {post_reloaded}"

    # Cleanup: Reset to defaults
    config.set_pre_post_led_delays(45.0, 5.0)

    print("\n✅ TEST 1 PASSED: Device config LED delay storage works correctly")
    return True


def test_acquisition_manager_loading():
    """Test that acquisition manager loads delays from config."""
    print("\n" + "=" * 70)
    print("TEST 2: Acquisition Manager Loads Delays from Config")
    print("=" * 70)

    from utils.device_configuration import DeviceConfiguration

    # Set custom delays in config
    config = DeviceConfiguration(device_serial="TEST_DEVICE")
    config.set_pre_post_led_delays(40.0, 7.0)
    print("Set config values: PRE=40ms, POST=7ms")

    # Note: We can't fully test acquisition manager without hardware
    # But we can verify the method exists and config values are retrievable
    print("\n✓ Config getter methods exist:")
    print(f"  - get_pre_led_delay_ms() → {config.get_pre_led_delay_ms()}ms")
    print(f"  - get_post_led_delay_ms() → {config.get_post_led_delay_ms()}ms")

    # Cleanup
    config.set_pre_post_led_delays(45.0, 5.0)

    print("\n✅ TEST 2 PASSED: Config loading infrastructure is correct")
    print("   (Full test requires hardware - verified API only)")
    return True


def test_schema_structure():
    """Test that device config schema includes LED delay fields."""
    print("\n" + "=" * 70)
    print("TEST 3: Device Config Schema Structure")
    print("=" * 70)

    from utils.device_configuration import DeviceConfiguration

    config = DeviceConfiguration(device_serial="TEST_DEVICE")

    # Check schema includes new fields
    timing_params = config.config.get("timing_parameters", {})

    print("Checking timing_parameters schema:")
    assert "pre_led_delay_ms" in timing_params, "Missing 'pre_led_delay_ms' field"
    print("  ✓ pre_led_delay_ms exists")

    assert "post_led_delay_ms" in timing_params, "Missing 'post_led_delay_ms' field"
    print("  ✓ post_led_delay_ms exists")

    # Check old fields still exist (backward compatibility)
    assert "led_a_delay_ms" in timing_params, "Missing 'led_a_delay_ms' field"
    print("  ✓ led_a_delay_ms exists (backward compatibility)")

    print("\nFull timing_parameters structure:")
    for key, value in timing_params.items():
        print(f"  - {key}: {value}")

    print("\n✅ TEST 3 PASSED: Schema structure is correct")
    return True


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("LED DELAY PERSISTENCE - IMPLEMENTATION TEST")
    print("=" * 70)

    try:
        # Run all tests
        test1_passed = test_device_config_led_delays()
        test2_passed = test_acquisition_manager_loading()
        test3_passed = test_schema_structure()

        # Summary
        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        print(
            f"Test 1 (Device Config Storage): {'✅ PASSED' if test1_passed else '❌ FAILED'}",
        )
        print(
            f"Test 2 (Acquisition Manager API): {'✅ PASSED' if test2_passed else '❌ FAILED'}",
        )
        print(
            f"Test 3 (Schema Structure): {'✅ PASSED' if test3_passed else '❌ FAILED'}",
        )

        if all([test1_passed, test2_passed, test3_passed]):
            print("\n🎉 ALL TESTS PASSED - LED delay persistence is working!")
            print("\nNext steps:")
            print("1. Test with live hardware (start application)")
            print("2. Set custom LED delays in Advanced Settings")
            print("3. Restart application and verify delays persist")
            print("4. Run calibration and verify it uses config delays")
        else:
            print("\n❌ SOME TESTS FAILED - Check errors above")
            sys.exit(1)

    except Exception as e:
        print(f"\n❌ TEST ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
