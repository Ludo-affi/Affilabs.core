"""
Compare Step 4 raw values vs Step 6 dark-subtracted values
The ONLY difference should be ~3000 counts (the dark level)
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

# Check if we have Step 4 diagnostic data
step4_diagnostics = Path("generated-files/diagnostics")
if step4_diagnostics.exists():
    step4_files = list(step4_diagnostics.glob("step4_raw_spol_diagnostic_*.png"))
    if step4_files:
        print(f"\n✅ Found {len(step4_files)} Step 4 diagnostic plot(s)")
        print("   (These show RAW S-pol values BEFORE dark subtraction)")
    else:
        print("\n❌ No Step 4 diagnostic plots found")
else:
    print("\n❌ No diagnostics directory found")

# Check if we have Step 6 diagnostic data
if step4_diagnostics.exists():
    step6_files = list(step4_diagnostics.glob("step6_sref_diagnostic_*.png"))
    if step6_files:
        print(f"✅ Found {len(step6_files)} Step 6 diagnostic plot(s)")
        print("   (These show DARK-SUBTRACTED S-ref values)")
    else:
        print("❌ No Step 6 diagnostic plots found")

print("\n" + "="*80)
print("EXPECTED RELATIONSHIP:")
print("="*80)
print("""
Step 4 Raw S-pol ≈ Step 6 S-ref + Dark Noise
OR
Step 6 S-ref ≈ Step 4 Raw S-pol - 3,000 counts

If Step 6 values are DRAMATICALLY different from Step 4 values (more than
±5,000 count difference), that indicates a problem:
  - LEDs not operating the same way
  - Integration time changed
  - Different spectral filtering
  - Hardware issue
""")

print("\n" + "="*80)
print("CHECKING FOR RED FLAGS:")
print("="*80)

# Expected dark level
expected_dark = 3000

# Estimate what Step 4 raw values should have been
print(f"\n🔍 If dark = ~{expected_dark:,} counts, then Step 4 raw S-pol should have been:")
print(f"   (Step 6 dark-subtracted + {expected_dark:,})")
print()

for ch in ['a', 'b', 'c', 'd']:
    if ch in s_ref_max:
        step6_value = s_ref_max[ch]
        expected_step4 = step6_value + expected_dark

        print(f"  Channel {ch.upper()}:")
        print(f"    Step 6 (dark-subtracted): {step6_value:>10,.1f} counts")
        print(f"    Expected Step 4 (raw):    {expected_step4:>10,.1f} counts")

        # Red flag check
        if ch == 'b' and step6_value >= 65535:
            print(f"    ⚠️  SATURATED - Channel B is at detector max")
        elif step6_value < 30000:
            print(f"    🚩 RED FLAG: Signal appears SUPPRESSED (too low)")
        elif step6_value > 60000:
            print(f"    🚩 RED FLAG: Signal appears TOO HIGH (approaching saturation)")
        else:
            print(f"    ✅ Signal level looks reasonable")
        print()

print("\n" + "="*80)
print("ACTION NEEDED:")
print("="*80)
print("""
1. Look at your Step 4 diagnostic plot (step4_raw_spol_diagnostic_*.png)
   - Note the ROI mean values in Panel 2

2. Look at your Step 6 diagnostic plot (step6_sref_diagnostic_*.png)
   - Note the ROI mean values in Panel 2

3. Calculate: Step 4 ROI mean - Step 6 ROI mean = ?
   - Should be approximately 3,000 counts (the dark level)
   - If difference is >5,000 or <1,000, that's a RED FLAG

4. If there IS a red flag:
   - Check if LEDs changed between steps
   - Check if integration time changed
   - Check if something happened to hardware
   - Check calibration logs for any warnings

Please share what you see in both diagnostic plots!
""")
