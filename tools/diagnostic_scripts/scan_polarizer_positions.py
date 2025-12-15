"""Scan polarizer positions to identify blocking vs. transmitting orientations.

This script sweeps through polarizer positions (0-255 servo scale) and measures
signal strength to identify which positions block light (dark noise ~3000) versus
which positions allow light through (useful signal).

This helps diagnose polarizer misconfiguration without running full OEM calibration.
"""

import sys
import time
from pathlib import Path

import numpy as np

# Add project root to path
ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

from utils.controller import PicoP4SPR
from utils.usb4000_oceandirect import USB4000OceanDirect

# Test parameters
INTEGRATION_TIME_MS = 32  # Fast scan
LED_CHANNEL = "c"  # Test with channel C
LED_INTENSITY = 255  # Maximum LED
POSITION_STEP = 5  # Scan every 5 positions (0-255 range)
SETTLE_TIME = 0.3  # Time for servo to reach position


def main():
    """Scan polarizer positions and identify blocking orientations."""
    print("=" * 80)
    print("POLARIZER POSITION SCANNER")
    print("=" * 80)
    print("Test Configuration:")
    print(f"  LED Channel: {LED_CHANNEL}")
    print(f"  LED Intensity: {LED_INTENSITY}")
    print(f"  Integration Time: {INTEGRATION_TIME_MS}ms")
    print(f"  Position Step: {POSITION_STEP} (0-255 servo scale)")
    print(f"  Settle Time: {SETTLE_TIME}s")
    print("=" * 80)
    print()

    # Initialize hardware
    print("🔌 Connecting to hardware...")
    ctrl = PicoP4SPR()
    usb = USB4000OceanDirect()

    if not ctrl.open():
        print("❌ Failed to connect to PicoP4SPR controller")
        return

    if not usb.connect():
        print("❌ Failed to connect to spectrometer")
        ctrl.close()
        return

    print("✅ Connected to controller")
    print("✅ Connected to spectrometer")
    print()

    try:
        # Set integration time
        usb.set_integration_time(INTEGRATION_TIME_MS / 1000.0)

        # Turn on test LED
        ctrl.set_intensity(LED_CHANNEL, LED_INTENSITY)
        time.sleep(0.5)  # Let LED stabilize

        # Prepare to scan positions
        positions = list(range(0, 256, POSITION_STEP))
        results = []

        print(f"🔍 Scanning {len(positions)} positions...")
        print()
        print("Position | Signal Max | Signal Mean | Status")
        print("-" * 60)

        # Scan through positions
        for pos in positions:
            # Set both S and P to same position for testing
            # (We're looking for the blocking orientation)
            ctrl.servo_set(s=pos, p=pos)
            time.sleep(SETTLE_TIME)

            # CRITICAL: Switch to S-mode to activate the polarizer window
            ctrl.set_mode("s")
            time.sleep(0.2)  # Let mode switch settle

            # Acquire spectrum
            spectrum = usb.acquire_spectrum()

            if spectrum is not None:
                signal_max = float(np.max(spectrum))
                signal_mean = float(np.mean(spectrum))

                # Classify position
                if signal_max < 5000:  # Near dark noise (< 7.6% of 65535)
                    status = "🚫 BLOCKING"
                elif signal_max < 20000:  # Low signal (< 30%)
                    status = "⚠️  WEAK"
                else:  # Good signal
                    status = "✅ GOOD"

                results.append(
                    {
                        "position": pos,
                        "max": signal_max,
                        "mean": signal_mean,
                        "status": status,
                    },
                )

                print(
                    f"{pos:4d}     | {signal_max:7.0f}    | {signal_mean:7.1f}     | {status}",
                )
            else:
                print(f"{pos:4d}     | ERROR acquiring spectrum")

        print()
        print("=" * 80)
        print("ANALYSIS")
        print("=" * 80)

        # Identify blocking positions
        blocking = [r for r in results if r["max"] < 5000]
        weak = [r for r in results if 5000 <= r["max"] < 20000]
        good = [r for r in results if r["max"] >= 20000]

        print(
            f"🚫 BLOCKING positions ({len(blocking)}): {[r['position'] for r in blocking]}",
        )
        if blocking:
            print(
                f"   Signal range: {min([r['max'] for r in blocking]):.0f} - {max([r['max'] for r in blocking]):.0f} counts",
            )
        print()

        print(f"⚠️  WEAK positions ({len(weak)}): {[r['position'] for r in weak]}")
        if weak:
            print(
                f"   Signal range: {min([r['max'] for r in weak]):.0f} - {max([r['max'] for r in weak]):.0f} counts",
            )
        print()

        print(f"✅ GOOD positions ({len(good)}): {[r['position'] for r in good]}")
        if good:
            print(
                f"   Signal range: {min([r['max'] for r in good]):.0f} - {max([r['max'] for r in good]):.0f} counts",
            )
            print()
            print(
                f"💡 RECOMMENDATION: Use polarizer position around {good[len(good)//2]['position']} (middle of good range)",
            )
        print()

        # Check current device configuration
        print("=" * 80)
        print("CURRENT DEVICE CONFIGURATION CHECK")
        print("=" * 80)

        from utils.device_configuration import DeviceConfiguration

        dev_config = DeviceConfiguration()

        if dev_config.load_configuration("TEST001"):
            s_pos = dev_config.get_polarizer_s_position()
            p_pos = dev_config.get_polarizer_p_position()

            print(f"Current S position: {s_pos}")
            print(f"Current P position: {p_pos}")
            print()

            # Check if current positions are in blocking range
            if s_pos in [r["position"] for r in blocking]:
                print(f"❌ PROBLEM FOUND: S position ({s_pos}) is in BLOCKING range!")
            elif s_pos in [r["position"] for r in weak]:
                print(f"⚠️  WARNING: S position ({s_pos}) is in WEAK range")
            else:
                print(f"✅ S position ({s_pos}) looks OK")

            if p_pos in [r["position"] for r in blocking]:
                print(f"❌ PROBLEM FOUND: P position ({p_pos}) is in BLOCKING range!")
            elif p_pos in [r["position"] for r in weak]:
                print(f"⚠️  WARNING: P position ({p_pos}) is in WEAK range")
            else:
                print(f"✅ P position ({p_pos}) looks OK")
        else:
            print("⚠️  Could not load device configuration")

        print()
        print("=" * 80)

    finally:
        # Cleanup
        print()
        print("🧹 Cleaning up...")
        ctrl.turn_off_channels()
        ctrl.close()
        usb.disconnect()
        print("✅ Hardware disconnected")


if __name__ == "__main__":
    main()
