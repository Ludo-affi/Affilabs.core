"""Test S-mode vs P-mode polarizer configuration.

The previous scan showed ALL positions saturate when S and P are equal.
This test specifically checks what happens when we use different S/P positions
and switch between S-mode and P-mode.
"""

import time
import numpy as np
from pathlib import Path
import sys

# Add project root to path
ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

from utils.controller import PicoP4SPR
from utils.usb4000_oceandirect import USB4000OceanDirect

# Test parameters
INTEGRATION_TIME_MS = 32
LED_CHANNEL = "c"
LED_INTENSITY = 255

def test_sp_config(ctrl, usb, s_pos, p_pos, desc="Test"):
    """Test a specific S/P configuration in both modes."""
    print(f"\n{desc}")
    print(f"  Servo positions: S={s_pos}, P={p_pos}")

    # Set servo positions
    ctrl.servo_set(s=s_pos, p=p_pos)
    time.sleep(0.5)  # Let servo settle

    # Test S-mode
    ctrl.set_mode("s")
    time.sleep(0.3)
    spectrum_s = usb.acquire_spectrum()
    if spectrum_s is not None:
        s_max = float(np.max(spectrum_s))
        s_mean = float(np.mean(spectrum_s))
        s_percent = (s_max / 65535) * 100
        print(f"  S-mode: max={s_max:.0f} ({s_percent:.1f}%), mean={s_mean:.0f}")
    else:
        print(f"  S-mode: ERROR acquiring spectrum")
        s_max = 0

    # Test P-mode
    ctrl.set_mode("p")
    time.sleep(0.3)
    spectrum_p = usb.acquire_spectrum()
    if spectrum_p is not None:
        p_max = float(np.max(spectrum_p))
        p_mean = float(np.mean(spectrum_p))
        p_percent = (p_max / 65535) * 100
        print(f"  P-mode: max={p_max:.0f} ({p_percent:.1f}%), mean={p_mean:.0f}")

        # Calculate S/P ratio
        if p_max > 0:
            sp_ratio = s_max / p_max
            print(f"  S/P ratio: {sp_ratio:.3f}")
    else:
        print(f"  P-mode: ERROR acquiring spectrum")

    return s_max, p_max if spectrum_p is not None else 0

def main():
    """Test S/P mode configurations."""

    print("=" * 80)
    print("S-MODE / P-MODE CONFIGURATION TEST")
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

    print(f"✅ Connected to hardware")
    print()

    try:
        # Set integration time
        usb.set_integration_time(INTEGRATION_TIME_MS / 1000.0)

        # Turn on test LED
        ctrl.set_intensity(LED_CHANNEL, LED_INTENSITY)
        time.sleep(0.5)

        print("=" * 80)
        print("TESTING DIFFERENT S/P CONFIGURATIONS")
        print("=" * 80)

        # Try to load current device configuration from JSON
        config_file = Path(ROOT_DIR) / "config" / "device_TEST001.json"
        current_s = 30  # Default
        current_p = 12  # Default

        if config_file.exists():
            try:
                import json
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    current_s = config.get('oem_calibration', {}).get('s_position', 30)
                    current_p = config.get('oem_calibration', {}).get('p_position', 12)
                print(f"\n📋 Loaded from {config_file.name}:")
                print(f"   S position: {current_s}")
                print(f"   P position: {current_p}")
            except Exception as e:
                print(f"\n⚠️  Error reading config: {e}")
                print(f"   Using defaults: S=30, P=12")
        else:
            print(f"\n⚠️  Config file not found: {config_file}")
            print(f"   Using defaults: S=30, P=12")

        # Test current configuration
        test_sp_config(ctrl, usb, current_s, current_p,
                      f"🔍 TEST 1: Current Device Config (S={current_s}, P={current_p})")

        # Test reversed configuration
        test_sp_config(ctrl, usb, current_p, current_s,
                      f"🔍 TEST 2: Reversed Config (S={current_p}, P={current_s})")

        # Test same position (both at S value)
        test_sp_config(ctrl, usb, current_s, current_s,
                      f"🔍 TEST 3: Both at S position (S={current_s}, P={current_s})")

        # Test same position (both at P value)
        test_sp_config(ctrl, usb, current_p, current_p,
                      f"🔍 TEST 4: Both at P position (S={current_p}, P={current_p})")

        # Test orthogonal positions (90 degrees apart in 0-180 range)
        # Servo 0-255 maps to 0-180 degrees, so 90 degrees ≈ 127 servo units
        s_test = 50
        p_test = s_test + 127  # 90 degrees apart
        if p_test > 180:  # Max servo position is 180
            p_test = 180
        test_sp_config(ctrl, usb, s_test, p_test,
                      f"🔍 TEST 5: 90° apart (S={s_test}, P={p_test})")

        # Test typical working positions from other devices
        test_sp_config(ctrl, usb, 80, 50,
                      "🔍 TEST 6: Typical config 1 (S=80, P=50)")

        test_sp_config(ctrl, usb, 100, 30,
                      "🔍 TEST 7: Typical config 2 (S=100, P=30)")

        print()
        print("=" * 80)
        print("ANALYSIS")
        print("=" * 80)
        print()
        print("💡 WHAT TO LOOK FOR:")
        print("   • S-mode should give STRONG signal (> 50% detector max)")
        print("   • P-mode should give WEAKER signal than S-mode")
        print("   • S/P ratio should be 2-4× (typical for SPR)")
        print("   • If BOTH modes show same signal, polarizer not working")
        print("   • If S-mode shows ~3000 counts, polarizer is blocking")
        print()

    finally:
        # Cleanup
        print("🧹 Cleaning up...")
        ctrl.turn_off_channels()
        ctrl.close()
        usb.disconnect()
        print("✅ Hardware disconnected")

if __name__ == "__main__":
    main()
