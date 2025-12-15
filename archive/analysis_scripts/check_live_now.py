"""Quick check of live integration time from device config."""

import json
import sys

config_path = r"C:\Users\lucia\OneDrive\Desktop\control-3.2.9\config\device_config.json"

try:
    with open(config_path) as f:
        config = json.load(f)

    if "led_calibration" in config:
        cal = config["led_calibration"]
        integration_ms = cal.get("integration_time_ms", "NOT FOUND")
        live_boost_ms = cal.get("live_boost_integration_ms", "NOT FOUND")

        print("\n" + "=" * 60)
        print("📊 CURRENT CALIBRATION DATA:")
        print("=" * 60)
        print(f"   Calibrated integration: {integration_ms} ms")
        print(f"   Live boost integration: {live_boost_ms} ms")

        if live_boost_ms != "NOT FOUND" and integration_ms != "NOT FOUND":
            boost_factor = live_boost_ms / integration_ms
            print(f"   Boost factor: {boost_factor:.2f}×")
            print()

            if live_boost_ms > 40:
                print("✅ SUCCESS! Integration time is BOOSTED (not 5ms)")
                print(f"   Live mode will use {live_boost_ms}ms instead of 5ms")
                print(
                    f"   Expected signal improvement: ~{live_boost_ms/5:.1f}× stronger",
                )
                sys.exit(0)
            else:
                print("❌ FAILED! Integration time is still too low")
                sys.exit(1)
        else:
            print("⚠️  Could not find calibration data")
            sys.exit(1)
    else:
        print("❌ No calibration data found")
        sys.exit(1)

except Exception as e:
    print(f"❌ Error reading config: {e}")
    sys.exit(1)
