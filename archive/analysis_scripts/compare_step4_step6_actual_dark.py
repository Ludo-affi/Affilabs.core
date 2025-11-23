"""
Compare Step 4 vs Step 6 with ACTUAL measured dark noise
(Not assumed ~3000 - that's specific to Ocean Optics/USB4000 class detectors)
"""
import json
import numpy as np
from pathlib import Path

# Load device config
with open('config/device_config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

led_cal = config.get('led_calibration', {})

print("\n" + "="*80)
print("STEP 4 vs STEP 6 SIGNAL COMPARISON")
print("="*80)

# Get Step 6 S-ref max intensities (dark-subtracted)
s_ref_max = led_cal.get('s_ref_max_intensity', {})

print("\n📊 Step 6 S-ref Maximum Intensities (DARK-SUBTRACTED):")
for ch in ['a', 'b', 'c', 'd']:
    if ch in s_ref_max:
        print(f"  Channel {ch.upper()}: {s_ref_max[ch]:,.1f} counts")

# Try to find ACTUAL measured dark noise from Step 5
print("\n" + "="*80)
print("CHECKING ACTUAL DARK NOISE (from Step 5 calibration)")
print("="*80)

calib_dir = Path("calibration_data")
dark_file = calib_dir / "dark_noise_latest.npy"

if dark_file.exists():
    try:
        dark_array = np.load(dark_file)
        dark_mean = np.mean(dark_array)
        dark_std = np.std(dark_array)
        dark_min = np.min(dark_array)
        dark_max = np.max(dark_array)

        print(f"\n✅ Loaded dark noise from: {dark_file}")
        print(f"   Mean:   {dark_mean:,.1f} counts")
        print(f"   Std:    {dark_std:,.1f} counts")
        print(f"   Min:    {dark_min:,.1f} counts")
        print(f"   Max:    {dark_max:,.1f} counts")

        # Calculate ROI mean (580-610nm region, approximately pixels 1700-1900)
        # This is detector-specific
        roi_start = len(dark_array) // 2  # rough estimate
        roi_end = roi_start + 200
        dark_roi_mean = np.mean(dark_array[roi_start:roi_end])
        print(f"   ROI Mean (approx 580-610nm): {dark_roi_mean:,.1f} counts")

        measured_dark = dark_roi_mean
        print(f"\n📌 Using MEASURED dark ROI mean: {measured_dark:,.1f} counts")

    except Exception as e:
        print(f"\n❌ Error loading dark noise: {e}")
        measured_dark = None
else:
    print(f"\n❌ Dark noise file not found: {dark_file}")
    print(f"   Expected location: calibration_data/dark_noise_latest.npy")
    measured_dark = None

# If we don't have measured dark, note the detector class default
if measured_dark is None:
    print(f"\n⚠️  No measured dark noise found.")
    print(f"   For Ocean Optics/USB4000 class detectors (like Flame-T),")
    print(f"   typical dark noise is ~3,000 counts @ 36ms integration.")
    print(f"   This is DETECTOR-SPECIFIC - other detectors will differ!")
    assumed_dark = 3000
    print(f"\n📌 Using ASSUMED dark for Ocean Optics: {assumed_dark:,.1f} counts")
    dark_value = assumed_dark
else:
    dark_value = measured_dark

print("\n" + "="*80)
print("EXPECTED STEP 4 RAW VALUES:")
print("="*80)
print(f"\nStep 4 Raw S-pol = Step 6 S-ref + Dark Noise")
print(f"                 = Step 6 S-ref + {dark_value:,.1f} counts")
print()

for ch in ['a', 'b', 'c', 'd']:
    if ch in s_ref_max:
        step6_value = s_ref_max[ch]
        expected_step4 = step6_value + dark_value

        print(f"Channel {ch.upper()}:")
        print(f"  Step 6 (dark-subtracted): {step6_value:>10,.1f} counts")
        print(f"  Expected Step 4 (raw):    {expected_step4:>10,.1f} counts")

        # Red flag check
        if ch == 'b' and step6_value >= 65535:
            print(f"  ⚠️  SATURATED - Channel B at detector max")
        elif step6_value < 30000:
            print(f"  🚩 RED FLAG: Signal appears SUPPRESSED")
        elif step6_value > 60000:
            print(f"  🚩 RED FLAG: Signal TOO HIGH (near saturation)")
        else:
            print(f"  ✅ Signal level reasonable")
        print()

print("="*80)
print("VERIFY AGAINST YOUR DIAGNOSTIC PLOTS:")
print("="*80)
print("""
Look at Panel 2 (ROI Means) in both diagnostic plots:

1. Step 4 diagnostic: step4_raw_spol_diagnostic_*.png
   - Shows RAW S-pol values BEFORE dark subtraction

2. Step 6 diagnostic: step6_sref_diagnostic_*.png
   - Shows DARK-SUBTRACTED S-ref values

For each channel, calculate:
  Difference = Step 4 ROI mean - Step 6 ROI mean

Expected difference: """ + f"{dark_value:,.0f} counts (+/- 500 counts is normal)")

print("""

🚩 RED FLAGS to look for:
  - Difference < 1,000 or > 5,000 counts
  - Step 6 dramatically lower than expected
  - LEDs changed between steps
  - Integration time changed

✅ GOOD if:
  - Difference is close to measured dark noise
  - Step 6 values are 45,000-52,000 range (except saturated Channel B)
  - Channels maintain relative balance
""")

print("\n" + "="*80)
print("DETECTOR CLASS NOTE:")
print("="*80)
print("""
Your detector: Flame-T (Ocean Optics/USB4000 class)
  - Typical dark noise: ~3,000 counts @ 36ms integration
  - 16-bit detector: 0-65,535 count range
  - Non-linear dark response: increases with integration time

Other detector classes will have different dark noise levels!
Always measure dark noise during calibration (Step 5).
""")
