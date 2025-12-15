"""Check Step 6 S-ref signals and dark levels to diagnose suppression."""

from pathlib import Path

import numpy as np

# Load calibration data
calib_dir = Path("calibration_data")

# Find latest dark and S-ref files
dark_latest = calib_dir / "dark_noise_latest.npy"
s_refs = {
    "a": calib_dir / "s_ref_a_latest.npy",
    "b": calib_dir / "s_ref_b_latest.npy",
    "c": calib_dir / "s_ref_c_latest.npy",
    "d": calib_dir / "s_ref_d_latest.npy",
}

print("=" * 80)
print("STEP 6 SIGNAL ANALYSIS")
print("=" * 80)
print()

# Check dark noise
if dark_latest.exists():
    dark = np.load(dark_latest)
    print("Dark Noise (Step 5):")
    print(f"  File: {dark_latest}")
    print(f"  Length: {len(dark)} pixels")
    print(f"  Mean: {np.mean(dark):.1f} counts")
    print(f"  Std: {np.std(dark):.1f} counts")
    print(f"  Min: {np.min(dark):.1f} counts")
    print(f"  Max: {np.max(dark):.1f} counts")
    print()
else:
    print("❌ No dark_noise_latest.npy found!")
    dark = None
    print()

# Check S-ref for each channel
print("S-ref Signals (Step 6, AFTER dark subtraction):")
print()

for ch, path in s_refs.items():
    if path.exists():
        s_ref = np.load(path)
        print(f"Channel {ch.upper()}:")
        print(f"  File: {path}")
        print(f"  Length: {len(s_ref)} pixels")
        print(f"  Mean: {np.mean(s_ref):.1f} counts")
        print(f"  Std: {np.std(s_ref):.1f} counts")
        print(f"  Min: {np.min(s_ref):.1f} counts")
        print(f"  Max: {np.max(s_ref):.1f} counts")

        # Calculate ROI (580-610nm approximate: pixels 1200-1400 if 3648 total)
        # This is rough approximation
        roi_start = len(s_ref) // 3
        roi_end = len(s_ref) // 2
        roi_mean = np.mean(s_ref[roi_start:roi_end])
        print(f"  ROI Mean (approx 580-610nm): {roi_mean:.1f} counts")

        # Check if signal looks suppressed (below expected ~49,000)
        if roi_mean < 30000:
            print("  ⚠️  WARNING: Signal appears SUPPRESSED (expected ~49,000)")

        print()
    else:
        print(f"❌ Channel {ch.upper()}: No s_ref_{ch}_latest.npy found!")
        print()

# If we have dark, check if it's reasonable (~3000 counts)
if dark is not None:
    if np.mean(dark) > 5000:
        print("⚠️  WARNING: Dark level is HIGH (>5000). Expected ~3000.")
    elif np.mean(dark) < 2000:
        print("⚠️  WARNING: Dark level is LOW (<2000). Expected ~3000.")
    else:
        print("✅ Dark level looks reasonable (~3000 counts)")

print()
print("=" * 80)
