"""Check S-ref signal levels from device_config.json"""

import json

# Load device config
with open("config/device_config.json") as f:
    config = json.load(f)

# Get LED calibration data
led_cal = config.get("led_calibration", {})

print("\n" + "=" * 80)
print("STEP 6 S-REF SIGNAL ANALYSIS FROM DEVICE_CONFIG")
print("=" * 80)

# Get S-ref max intensities (peak values in ROI)
s_ref_max = led_cal.get("s_ref_max_intensity", {})
print("\n📊 S-ref Maximum Intensities (from ROI):")
for ch in ["a", "b", "c", "d"]:
    if ch in s_ref_max:
        print(f"  Channel {ch.upper()}: {s_ref_max[ch]:,.1f} counts")

# Get baseline S-ref means (full spectrum average)
baseline = config.get("baseline_data", {})
s_ref_mean = baseline.get("s_ref_mean", {})
print("\n📊 S-ref Mean Values (full spectrum):")
for ch in ["a", "b", "c", "d"]:
    if ch in s_ref_mean:
        print(f"  Channel {ch.upper()}: {s_ref_mean[ch]:,.1f} counts")

# Get LED values used
led_intensities = led_cal.get("live_boost_led_intensities", {})
print("\n💡 LED Intensities Used:")
for ch in ["a", "b", "c", "d"]:
    if ch in led_intensities:
        print(f"  Channel {ch.upper()}: {led_intensities[ch]}")

# Get integration time
integration_ms = led_cal.get("live_boost_integration_ms", None)
print(f"\n⏱️  Integration Time: {integration_ms} ms")

# Calculate expected values
print("\n" + "=" * 80)
print("ANALYSIS - Are Signals Suppressed?")
print("=" * 80)

print("\n📌 Expected Dark Level: ~3,000 counts")
print("📌 Target Signal (75% of detector max): 49,151 counts")
print("📌 Detector Maximum: 65,535 counts")

print("\n✅ STEP 4 (Raw S-pol before dark subtraction):")
print("   - Should see signals around 52,000 counts")
print("   - This is: Target (49,151) + Dark (3,000) = ~52,000")

print("\n✅ STEP 6 (Dark-subtracted S-ref ready for live):")
print("   - Should see signals around 49,000 counts")
print("   - This is: Raw (52,000) - Dark (3,000) = ~49,000")

print("\n🔍 Your Step 6 S-ref Max Intensities:")
for ch in ["a", "b", "c", "d"]:
    if ch in s_ref_max:
        value = s_ref_max[ch]
        if 45000 <= value <= 53000:
            status = "✅ GOOD"
        elif value < 45000:
            status = "⚠️  LOW (suppressed?)"
        else:
            status = "⚠️  HIGH"
        print(f"  Channel {ch.upper()}: {value:,.1f} counts {status}")

print("\n" + "=" * 80)
print("CONCLUSION")
print("=" * 80)
print("""
If your Step 6 values are around 45,000-50,000 counts:
- ✅ This is CORRECT! Dark subtraction is working.
- ✅ Signals appear "lower" than Step 4 because dark was removed.
- ✅ This is the expected final signal for live acquisition.

If your Step 4 values were ~52,000 and Step 6 values are ~49,000:
- ✅ Perfect! Dark subtraction removed ~3,000 counts as expected.

The "suppression" you're seeing is NORMAL and EXPECTED after dark subtraction!
""")
