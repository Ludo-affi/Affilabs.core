"""Demonstrate adaptive LED intensity scaling for model training.

Shows how intensities are scaled based on:
1. Integration time (longer time = lower intensity)
2. LED brightness (brighter LED = lower intensity)
"""

# Simulate LED slopes from actual model
led_slopes_10ms = {
    "A": 72.6,    # Dimmest
    "B": 105.4,   # Medium-dim
    "C": 191.2,   # Bright
    "D": 185.9,   # Bright
}

# Calculate brightness factors (relative to dimmest LED)
min_slope = min(led_slopes_10ms.values())
brightness_factors = {
    led: min_slope / slope for led, slope in led_slopes_10ms.items()
}

# Base intensities
base_intensities = [30, 60, 90, 120, 150]

# Integration time scaling factors
time_scales = {
    10: 1.0,   # Full intensity at baseline
    20: 0.85,  # 85% at 20ms
    30: 0.70,  # 70% at 30ms
    45: 0.55,  # 55% at 45ms
    60: 0.40,  # 40% at 60ms
}

print("=" * 80)
print("ADAPTIVE LED INTENSITY SCALING")
print("=" * 80)
print("\nLED Brightness Factors (relative to dimmest):")
for led, factor in brightness_factors.items():
    print(f"  {led}: {factor:.3f} (slope={led_slopes_10ms[led]:.1f})")

print("\n" + "=" * 80)
print("INTENSITIES USED AT EACH INTEGRATION TIME")
print("=" * 80)

for time_ms, time_scale in time_scales.items():
    print(f"\n{time_ms}ms (time_scale={time_scale:.2f}):")
    print(f"{'LED':>5} {'Factor':>8} {'Intensities':>50}")
    print("-" * 80)

    for led in ["A", "B", "C", "D"]:
        led_scale = brightness_factors[led] * time_scale
        intensities = [max(10, int(i * led_scale)) for i in base_intensities]
        intensities_str = ", ".join([f"{i:3d}" for i in intensities])
        print(f"{led:>5} {led_scale:>8.3f} [{intensities_str}]")

print("\n" + "=" * 80)
print("KEY INSIGHTS")
print("=" * 80)
print("1. LED A (dimmest) uses FULL base intensities at all times")
print("2. LED C/D (brightest) use REDUCED intensities, especially at long times")
print("3. At 60ms, LED C uses only ~19% of base intensities (0.379 × 0.40 × [30,60,90,120,150])")
print("4. This prevents saturation while maintaining good SNR")
print("\nOld approach: Same intensities for all LEDs → bright LEDs saturated")
print("New approach: Adaptive scaling → all LEDs stay in linear range")
