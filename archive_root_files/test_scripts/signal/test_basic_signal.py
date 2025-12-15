"""Basic signal test - Verify detector sees LED light at 20% intensity.

Tests the most fundamental acquisition:
- Flash each LED at 20% (51/255)
- Integrate for 70ms
- Read spectrum
- Display signal statistics

This validates:
1. Detector is connected and reading
2. LEDs are turning on
3. Integration time is being set
4. Light is reaching the detector
"""

import os
import sys

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import time

import numpy as np

from utils.controller import PicoP4SPR
from utils.usb4000_wrapper import USB4000

# Configuration
LED_INTENSITY = 51  # 20% of 255
INTEGRATION_TIME_MS = 70
LED_DELAY_MS = 45  # Time for LED to stabilize
CHANNELS = ["a", "b", "c", "d"]


def main():
    print("=" * 80)
    print("BASIC SIGNAL TEST - LED 20%, Integration 70ms")
    print("=" * 80)
    print()

    # Connect to hardware
    print("🔌 Connecting to hardware...")
    ctrl = PicoP4SPR()
    if not ctrl.open():
        print("❌ Controller not connected!")
        return
    print(f"✅ Controller connected: Firmware {ctrl.version}")

    usb = USB4000()
    if not usb.open():
        print("❌ Detector not connected!")
        ctrl.close()
        return
    print(f"✅ Detector connected: {usb.serial_number}")
    print()

    # Set integration time
    print(f"⏱️  Setting integration time: {INTEGRATION_TIME_MS}ms")
    integration_seconds = INTEGRATION_TIME_MS / 1000.0
    usb.set_integration(INTEGRATION_TIME_MS)
    time.sleep(0.1)
    print()

    # Ensure all LEDs start OFF
    print("💡 Turning all LEDs OFF...")
    ctrl.turn_off_channels()
    time.sleep(0.2)
    print()

    # Test each channel
    print("=" * 80)
    print("TESTING CHANNELS")
    print("=" * 80)
    print()

    for ch in CHANNELS:
        print(f"Channel {ch.upper()}:")
        print(f"  Setting LED to {LED_INTENSITY} ({LED_INTENSITY/255*100:.0f}%)")

        # Turn on LED
        ctrl.set_intensity(ch=ch, raw_val=LED_INTENSITY)

        # Wait for LED to stabilize
        time.sleep(LED_DELAY_MS / 1000.0)

        # Read spectrum
        print("  Reading spectrum...")
        spectrum = usb.read_intensity()

        # Turn off LED
        ctrl.set_intensity(ch=ch, raw_val=0)
        time.sleep(0.05)

        if spectrum is None:
            print("  ❌ FAILED: No spectrum data!")
            continue

        # Analyze signal
        min_val = np.min(spectrum)
        max_val = np.max(spectrum)
        mean_val = np.mean(spectrum)
        std_val = np.std(spectrum)

        print("  ✅ SUCCESS:")
        print(f"     Pixels: {len(spectrum)}")
        print(f"     Min:    {min_val:8.1f} counts")
        print(f"     Max:    {max_val:8.1f} counts")
        print(f"     Mean:   {mean_val:8.1f} counts")
        print(f"     StdDev: {std_val:8.1f} counts")

        # Check if we have signal (max should be significantly higher than min)
        signal_range = max_val - min_val
        if signal_range > 1000:
            print(f"     🟢 GOOD SIGNAL (range: {signal_range:.0f} counts)")
        elif signal_range > 100:
            print(f"     🟡 WEAK SIGNAL (range: {signal_range:.0f} counts)")
        else:
            print(f"     🔴 NO SIGNAL (range: {signal_range:.0f} counts)")

        print()

    # Measure dark noise for reference
    print("=" * 80)
    print("DARK NOISE MEASUREMENT")
    print("=" * 80)
    print()

    print("Ensuring all LEDs OFF...")
    ctrl.turn_off_channels()
    time.sleep(0.2)

    print("Reading dark spectrum...")
    dark = usb.read_intensity()

    if dark is not None:
        dark_min = np.min(dark)
        dark_max = np.max(dark)
        dark_mean = np.mean(dark)
        dark_std = np.std(dark)

        print("Dark Noise:")
        print(f"  Min:    {dark_min:8.1f} counts")
        print(f"  Max:    {dark_max:8.1f} counts")
        print(f"  Mean:   {dark_mean:8.1f} counts")
        print(f"  StdDev: {dark_std:8.1f} counts")
        print()

        if dark_mean > 5000:
            print("⚠️  WARNING: High dark noise! Check for light leaks.")
        else:
            print("✅ Dark noise looks normal.")
    else:
        print("❌ Could not read dark spectrum!")

    print()
    print("=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)

    # Cleanup
    ctrl.turn_off_channels()
    usb.close()
    ctrl.close()


if __name__ == "__main__":
    main()
