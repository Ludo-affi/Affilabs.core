"""Quick diagnostic to check current polarizer position"""

import sys
import time
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path(__file__).parent))

import logging

from utils.controller import PicoP4SPR
from utils.usb4000_oceandirect import USB4000OceanDirect

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main():
    print("=" * 70)
    print("POLARIZER POSITION DIAGNOSTIC")
    print("=" * 70)

    # Initialize hardware
    ctrl = PicoP4SPR()
    usb = USB4000OceanDirect()

    # Connect
    if not ctrl.connect():
        print("❌ Failed to connect to controller")
        return

    if not usb.connect():
        print("❌ Failed to connect to spectrometer")
        ctrl.close()
        return

    print("\n✅ Hardware connected")

    # Test both modes
    print("\n" + "=" * 70)
    print("TESTING S-MODE")
    print("=" * 70)

    result = ctrl.set_mode("s")
    print(f"Command result: {result}")
    time.sleep(0.5)

    # Measure signal
    ctrl.activate_channel("a")
    time.sleep(0.05)
    spectrum_s = usb.read_intensity()
    ctrl.deactivate_channel("a")

    if spectrum_s is not None:
        import numpy as np

        max_s = np.max(spectrum_s)
        mean_s = np.mean(spectrum_s)
        print(f"S-mode signal: max={max_s:.0f}, mean={mean_s:.0f} counts")
        if max_s >= 65535:
            print("⚠️  SATURATED - likely in P-mode position!")
        else:
            print("✅ Normal signal - likely in S-mode position")

    # Test P-mode
    print("\n" + "=" * 70)
    print("TESTING P-MODE")
    print("=" * 70)

    result = ctrl.set_mode("p")
    print(f"Command result: {result}")
    time.sleep(0.5)

    # Measure signal
    ctrl.activate_channel("a")
    time.sleep(0.05)
    spectrum_p = usb.read_intensity()
    ctrl.deactivate_channel("a")

    if spectrum_p is not None:
        max_p = np.max(spectrum_p)
        mean_p = np.mean(spectrum_p)
        print(f"P-mode signal: max={max_p:.0f}, mean={mean_p:.0f} counts")
        if max_p >= 65535:
            print("✅ SATURATED - correct for P-mode (sensor resonance)")
        else:
            print("⚠️  Low signal - might be stuck in S-mode position!")

    # Compare
    print("\n" + "=" * 70)
    print("COMPARISON")
    print("=" * 70)

    if spectrum_s is not None and spectrum_p is not None:
        ratio = max_p / max(max_s, 1)
        print(f"\nP/S ratio: {ratio:.1f}:1")
        print("\nExpected behavior:")
        print("  S-mode: Low signal (no sensor resonance)")
        print("  P-mode: High signal (sensor resonance, often saturated)")
        print("\nActual behavior:")
        print(f"  S-mode: max={max_s:.0f} {'[SATURATED]' if max_s >= 65535 else ''}")
        print(f"  P-mode: max={max_p:.0f} {'[SATURATED]' if max_p >= 65535 else ''}")

        if max_s >= 65535 and max_p < 30000:
            print(
                "\n🚨 POLARIZER REVERSED! S-mode showing P-signal, P-mode showing S-signal",
            )
        elif max_s < 30000 and max_p >= 65535:
            print("\n✅ POLARIZER CORRECT! S-mode low, P-mode high")
        else:
            print("\n⚠️  UNCLEAR - check servo positions or LED calibration")

    # Cleanup
    ctrl.close()
    usb.close()


if __name__ == "__main__":
    main()
