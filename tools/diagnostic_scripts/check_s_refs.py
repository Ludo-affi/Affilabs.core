import os

import numpy as np

os.chdir("generated-files/calibration_data")

print("S-mode Reference Signals - Saturation Check")
print("=" * 60)
print("Threshold: 62,000 counts (95% of 65,535 max)")
print()

for ch in ["a", "b", "c", "d"]:
    filename = f"s_ref_{ch}_latest.npy"
    data = np.load(filename)

    max_val = data.max()
    mean_val = data.mean()
    region_580_600 = data[105:220].max()  # Approximate pixel range for 580-600nm
    saturated = "YES" if max_val > 62000 else "NO"

    print(f"Channel {ch.upper()}:")
    print(f"  Max:        {max_val:>8.0f} counts")
    print(f"  Mean:       {mean_val:>8.0f} counts")
    print(f"  580-600nm:  {region_580_600:>8.0f} counts")
    print(f"  SATURATED:  {saturated}")
    print()
