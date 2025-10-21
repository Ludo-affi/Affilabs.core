"""Diagnostic script to check sensorgram data structure."""

import json
import numpy as np

# Check what's in the generated config
print("=" * 80)
print("CHECKING GENERATED CONFIG")
print("=" * 80)

try:
    with open("generated-files/config.json", "r") as f:
        config = json.load(f)

    print("\n📋 Calibration data found:")
    print(f"  Integration time: {config.get('integration_time', 'N/A')}")
    print(f"  Min wavelength: {config.get('min_wavelength', 'N/A')}")
    print(f"  Max wavelength: {config.get('max_wavelength', 'N/A')}")

    # Check for channel-specific settings
    for ch in ["a", "b", "c", "d"]:
        ch_key = f"channel_{ch}"
        if ch_key in config:
            print(f"\n  Channel {ch.upper()}: {config[ch_key]}")

        # Check for intensities
        int_key = f"{ch}_intensity"
        if int_key in config:
            print(f"    {int_key}: {config[int_key]}")

except FileNotFoundError:
    print("❌ No generated-files/config.json found - calibration not run yet")
except Exception as e:
    print(f"❌ Error reading config: {e}")

# Check if there's a device config with channel info
print("\n" + "=" * 80)
print("CHECKING DEVICE CONFIG")
print("=" * 80)

try:
    with open("config/device_config.json", "r") as f:
        device_config = json.load(f)

    print("\n📋 Device configuration:")
    for key, value in device_config.items():
        if "channel" in key.lower() or key in ["a", "b", "c", "d"]:
            print(f"  {key}: {value}")

    print(f"\n  Controller type: {device_config.get('ctrl', 'N/A')}")
    print(f"  Detector type: {device_config.get('det', 'N/A')}")

except FileNotFoundError:
    print("❌ No config/device_config.json found")
except Exception as e:
    print(f"❌ Error reading device config: {e}")

print("\n" + "=" * 80)
print("SENSORGRAM DATA STRUCTURE EXPECTED")
print("=" * 80)

print("""
The sensorgram_data() method should return:
{
    "lambda_values": {
        "a": np.array([...]),  # Raw wavelength fit values
        "b": np.array([...]),
        "c": np.array([...]),
        "d": np.array([...])   # ⚠️ CHECK IF THIS EXISTS!
    },
    "lambda_times": {
        "a": np.array([...]),  # Timestamps
        "b": np.array([...]),
        "c": np.array([...]),
        "d": np.array([...])   # ⚠️ CHECK IF THIS EXISTS!
    },
    "buffered_lambda_values": {...},  # Post-filtering buffered values
    "filtered_lambda_values": {...},  # Median-filtered values
    "buffered_lambda_times": {...},
    "filt": bool,  # Whether filtering is on
    "start": float,  # Experiment start time
    "rec": bool,  # Whether recording
}

⚠️ POTENTIAL ISSUES:
1. Channel 'd' arrays might be empty (not initialized)
2. Channel 'd' might have all NaN values (low signal flagged during calibration)
3. Channel 'd' might not be in the active channel list
4. GUI might not be displaying channel 'd' even if data exists
""")

print("\n" + "=" * 80)
print("RECOMMENDATION")
print("=" * 80)
print("""
To diagnose, we need to:
1. Check if lambda_values['d'] exists and has data
2. Check if lambda_values['d'] contains real values or just NaNs
3. Check if the GUI is configured to display all 4 channels
4. Check logs for "Channel d: Signal low" warnings during calibration
""")
