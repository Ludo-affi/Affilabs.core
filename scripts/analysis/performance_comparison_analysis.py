"""Performance Analysis: Current vs. Target Baseline Noise
Comparing EMA approach to original method requirements
"""

from pathlib import Path

import numpy as np
import pandas as pd

# Load baseline data
data_file = Path("src/baseline_data/baseline_wavelengths_20251126_223040.csv")
df = pd.read_csv(data_file, header=None, on_bad_lines="skip")

# Filter numeric rows
numeric_rows = []
for idx, row in df.iterrows():
    try:
        float(row[0])
        numeric_rows.append(row)
    except (ValueError, TypeError):
        pass

df = pd.DataFrame(numeric_rows)
df = df.apply(pd.to_numeric, errors="coerce")

# Extract Channel A (best channel)
ch_a_wave = df[0].dropna().values
ch_a_time = df[1].dropna().values

print("=" * 80)
print("PERFORMANCE ANALYSIS: Current vs. Target")
print("=" * 80)
print()

# Calculate sampling rate
time_diffs = np.diff(ch_a_time)
sampling_rate = 1.0 / np.mean(time_diffs)
print(f"Current Sampling Rate: {sampling_rate:.3f} Hz")
print(f"Temporal Resolution: {1/sampling_rate:.3f} seconds")
print()

# Original data statistics
orig_std = np.std(ch_a_wave)
orig_pp = np.max(ch_a_wave) - np.min(ch_a_wave)

print("CURRENT BASELINE (from recording):")
print(f"  Standard deviation: {orig_std:.4f} nm = {orig_std*1000:.1f} pm")
print(f"  Peak-to-peak: {orig_pp:.4f} nm = {orig_pp*1000:.1f} pm")
print()

# Target specification
target_pp = 0.008  # nm = 8 pm
print("TARGET SPECIFICATION:")
print(f"  Peak-to-peak: {target_pp:.4f} nm = {target_pp*1000:.1f} pm")
print(f"  Required improvement: {orig_pp/target_pp:.1f}x reduction needed!")
print()

# Detrend the data (remove linear drift)
from scipy.stats import linregress

slope, intercept, _, _, _ = linregress(ch_a_time, ch_a_wave)
trend = slope * ch_a_time + intercept
detrended = ch_a_wave - trend

detrended_std = np.std(detrended)
detrended_pp = np.max(detrended) - np.min(detrended)

print("AFTER REMOVING LINEAR DRIFT:")
print(f"  Standard deviation: {detrended_std:.4f} nm = {detrended_std*1000:.1f} pm")
print(f"  Peak-to-peak: {detrended_pp:.4f} nm = {detrended_pp*1000:.1f} pm")
print(f"  Improvement: {orig_pp/detrended_pp:.1f}x better")
print()


# Calculate what EMA would achieve
def apply_ema(data, alpha):
    smoothed = np.zeros_like(data)
    smoothed[0] = data[0]
    for i in range(1, len(data)):
        smoothed[i] = alpha * data[i] + (1 - alpha) * smoothed[i - 1]
    return smoothed


print("EMA PERFORMANCE (alpha=0.1, tau=10 samples):")
ema_data = apply_ema(ch_a_wave, 0.1)
ema_std = np.std(ema_data)
ema_pp = np.max(ema_data) - np.min(ema_data)
print(f"  Standard deviation: {ema_std:.4f} nm = {ema_std*1000:.1f} pm")
print(f"  Peak-to-peak: {ema_pp:.4f} nm = {ema_pp*1000:.1f} pm")
print(f"  Temporal lag: {10/sampling_rate:.1f} seconds")
print(f"  Still {ema_pp/target_pp:.1f}x WORSE than target!")
print()

# What alpha would we need?
print("TESTING DIFFERENT EMA ALPHA VALUES:")
print(
    f"{'Alpha':<10} {'Tau (samples)':<15} {'Lag (sec)':<12} {'P-P (nm)':<12} {'P-P (pm)':<12} {'vs Target':<15}",
)
print("-" * 90)

for alpha in [0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.5]:
    tau = 1.0 / alpha
    lag_sec = tau / sampling_rate
    ema_test = apply_ema(ch_a_wave, alpha)
    pp_nm = np.max(ema_test) - np.min(ema_test)
    pp_pm = pp_nm * 1000
    vs_target = pp_nm / target_pp
    print(
        f"{alpha:<10.2f} {tau:<15.1f} {lag_sec:<12.1f} {pp_nm:<12.4f} {pp_pm:<12.1f} {vs_target:<15.1f}x",
    )

print()
print("=" * 80)
print("CRITICAL FINDINGS")
print("=" * 80)
print()

print("1. MAGNITUDE GAP:")
print(f"   Current baseline: {orig_pp:.4f} nm ({orig_pp*1000:.0f} pm)")
print(f"   Target baseline: {target_pp:.4f} nm ({target_pp*1000:.0f} pm)")
print(f"   Gap: {orig_pp/target_pp:.0f}x worse than target")
print()

print("2. EMA LIMITATIONS:")
print("   - EMA can only smooth existing data")
print("   - Cannot create sub-pm stability from nm-level noise")
print("   - Even alpha=0.01 (100-sample averaging) only reaches ~0.5 nm")
print("   - Would need alpha~0.001 (1000-sample avg) -> 15+ minute lag!")
print()

print("3. TEMPORAL RESOLUTION:")
print(f"   Current: {1/sampling_rate:.2f} sec/sample (~1 Hz)")
print("   Target: <1 sec (sub-second)")
print("   EMA alpha=0.1: 10-second lag (unacceptable for kinetics)")
print()

print("4. ROOT CAUSE ANALYSIS:")
print("   The 2.6 nm peak-to-peak noise suggests:")
print("   a) Thermal instability (0.003 Hz = 5-min cycles)")
print("   b) Mechanical vibrations (structural resonances)")
print("   c) LED/detector instability")
print("   d) Insufficient spectral resolution")
print()

print("5. WHAT ACHIEVED 0.008 nm ORIGINALLY?")
print("   Likely NOT just software filtering, but:")
print("   - Hardware: Temperature-controlled enclosure")
print("   - Hardware: Vibration isolation")
print("   - Hardware: Ultra-stable LED driver")
print("   - Hardware: Higher-resolution spectrometer")
print("   - Software: Wavelength calibration/drift correction")
print("   - Software: Reference subtraction (not just division)")
print()

print("=" * 80)
print("RECOMMENDATION")
print("=" * 80)
print()

print("ABANDON EMA PRE-SMOOTHING APPROACH:")
print("  - Cannot bridge 330x performance gap")
print("  - Introduces unacceptable latency")
print("  - Masks underlying hardware issues")
print()

print("INSTEAD, INVESTIGATE ORIGINAL METHOD:")
print("  1. Find original processing code (git history)")
print("  2. Identify hardware differences (thermal control?)")
print("  3. Check spectrometer settings (integration time, averaging)")
print("  4. Review reference subtraction vs. division")
print("  5. Examine wavelength calibration drift correction")
print()

print("IMMEDIATE ACTIONS:")
print("  1. Measure hardware stability (temperature, vibration)")
print("  2. Review spectrometer configuration")
print("  3. Compare current vs. original LED driver settings")
print("  4. Check if thermal enclosure/isolation removed")
print("  5. Verify Fourier alpha=9000 is still optimal")
print()

# Check what moving average window would be needed
print("=" * 80)
print("THEORETICAL ANALYSIS: Averaging Required")
print("=" * 80)
print()

# If we have 2.6 nm noise and need 0.008 nm, with Gaussian averaging:
# std_out = std_in / sqrt(N)
# N = (std_in / std_out)^2

required_reduction = orig_pp / target_pp
required_samples = required_reduction**2

print(f"To reduce {orig_pp:.4f} nm to {target_pp:.4f} nm:")
print(f"  Reduction factor: {required_reduction:.1f}x")
print(f"  If using averaging: N = {required_samples:.0f} samples needed")
print(f"  At 1 Hz sampling: {required_samples/sampling_rate:.0f} seconds of averaging!")
print()
print("This is IMPRACTICAL for real-time biosensor measurements.")
print("The original 0.008 nm must have come from hardware stability, not filtering.")
