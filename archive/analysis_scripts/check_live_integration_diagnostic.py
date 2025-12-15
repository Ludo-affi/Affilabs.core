"""Quick diagnostic to check integration time in live mode.

Run this after calibration completes and before starting live data.
Shows what integration time the spectrometer actually has.
"""

import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))


def check_live_integration():
    """Check integration time configuration for live mode."""
    print("\n" + "=" * 80)
    print("🔍 LIVE MODE INTEGRATION TIME DIAGNOSTIC")
    print("=" * 80)

    try:
        # Try to load calibration data
        from utils.device_configuration import DeviceConfiguration

        config = DeviceConfiguration()

        # Get calibration data
        led_cal = config.load_led_calibration()

        if not led_cal:
            print("❌ No LED calibration found in device_config.json")
            return

        print("\n📊 CALIBRATION DATA:")
        print(
            f"   Integration time (calibrated): {led_cal.get('integration_time_ms', 'N/A')} ms",
        )

        # Check for live boost settings
        live_boost_int = led_cal.get("live_boost_integration_ms")
        live_boost_factor = led_cal.get("live_boost_factor", 1.0)

        if live_boost_int:
            print("\n🚀 SMART BOOST SETTINGS:")
            print(f"   Live boost integration: {live_boost_int} ms")
            print(f"   Boost factor: {live_boost_factor:.2f}×")
            print(
                f"   LED intensities: {led_cal.get('live_boost_led_intensities', {})}",
            )
        else:
            print("\n⚠️  No live boost settings found in calibration")

        # Check settings.py defaults
        from settings import (
            LIVE_MODE_MAX_BOOST_FACTOR,
            LIVE_MODE_TARGET_INTENSITY_PERCENT,
            MIN_INTEGRATION,
            TARGET_INTENSITY_PERCENT,
        )

        print("\n⚙️  SETTINGS.PY DEFAULTS:")
        print(
            f"   MIN_INTEGRATION: {MIN_INTEGRATION} ms  ⚠️ THIS IS THE PROBLEM IF USED IN LIVE!",
        )
        print(f"   Max boost factor: {LIVE_MODE_MAX_BOOST_FACTOR}×")
        print(f"   Target intensity (cal): {TARGET_INTENSITY_PERCENT}%")
        print(f"   Target intensity (live): {LIVE_MODE_TARGET_INTENSITY_PERCENT}%")

        # Calculate expected boost
        cal_int = led_cal.get("integration_time_ms", MIN_INTEGRATION)
        expected_boost = cal_int * LIVE_MODE_MAX_BOOST_FACTOR

        print("\n🎯 EXPECTED LIVE INTEGRATION:")
        print(
            f"   {cal_int} ms × {LIVE_MODE_MAX_BOOST_FACTOR} = {expected_boost:.1f} ms",
        )

        if live_boost_int:
            if abs(live_boost_int - expected_boost) < 1.0:
                print(
                    f"   ✅ Stored boost matches expected: {live_boost_int} ms ≈ {expected_boost:.1f} ms",
                )
            else:
                print(
                    f"   ⚠️  Stored boost differs: {live_boost_int} ms vs {expected_boost:.1f} ms expected",
                )

        print("\n" + "=" * 80)
        print("🔍 DIAGNOSIS:")
        if live_boost_int and live_boost_int > MIN_INTEGRATION:
            print(f"   ✅ Smart boost is configured ({live_boost_int} ms)")
            print("   ⚠️  BUT: Check if this is ACTUALLY applied to the spectrometer!")
            print("   👉 Look for log messages:")
            print("      '✅ Applied boosted integration time to data_acquisition.usb'")
        else:
            print(
                f"   ❌ No valid boost configured - will default to {MIN_INTEGRATION} ms!",
            )
            print("   👉 This explains the weak signal issue")
        print("=" * 80 + "\n")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    check_live_integration()
