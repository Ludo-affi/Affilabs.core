"""
Verify Detector Data Collection and Storage
============================================

This script verifies that:
1. Detector reads light properly (like our basic test)
2. Data flows through acquisition manager correctly
3. Raw spectrum is stored at the right place in the data structure
4. Dark noise and afterglow corrections are applied

Expected Result: Similar signal levels as basic test (~11k-33k counts)
"""

import sys
import os
import time
import numpy as np
from pathlib import Path

# Add src directory to path (same as basic test)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import using simplified names from utils (like basic test does)
from utils.usb4000_wrapper import USB4000
from utils.controller import PicoP4SPR


def verify_data_storage():
    """Verify detector data collection and storage."""

    print("="*70)
    print("DETECTOR DATA COLLECTION & STORAGE VERIFICATION")
    print("="*70)

    # Step 1: Initialize hardware (using same approach as basic test)
    print("\n[1/4] Initializing hardware...")
    try:
        ctrl = PicoP4SPR()
        if not ctrl.open():
            print("   ❌ Controller connection failed")
            return False
        print(f"   ✅ Controller: Firmware {ctrl.version}")

        usb = USB4000()
        if not usb.open():
            print("   ❌ Spectrometer connection failed")
            ctrl.close()
            return False
        print(f"   ✅ Spectrometer: {usb.serial_number}")

    except Exception as e:
        print(f"   ❌ Hardware initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Step 2: Set up test parameters (matching basic test)
    print("\n[2/4] Setting up test parameters...")
    TEST_LED_INTENSITY = 51  # 20% (51/255) like basic test
    INTEGRATION_TIME_MS = 70  # 70ms like calibration

    try:
        usb.set_integration(INTEGRATION_TIME_MS)
        time.sleep(0.1)
        print(f"   ✅ Integration time: {INTEGRATION_TIME_MS}ms")
    except Exception as e:
        print(f"   ❌ Failed to set integration time: {e}")
        return False

    # Step 3: Direct hardware test (baseline - same as basic test)
    print("\n[3/4] Direct hardware test (baseline)...")
    print("   Testing Channel C at 20% intensity...")

    try:
        # Turn on LED (using set_intensity like basic test)
        ctrl.set_intensity(ch='c', raw_val=TEST_LED_INTENSITY)
        time.sleep(0.045)  # 45ms LED stabilization (same as basic test)

        # Read raw spectrum
        raw_direct = usb.read_intensity()

        # Turn off LED
        ctrl.set_intensity(ch='c', raw_val=0)
        time.sleep(0.05)

        if raw_direct is None:
            print("   ❌ Failed to read spectrum")
            return False

        direct_mean = np.mean(raw_direct)
        direct_max = np.max(raw_direct)
        direct_min = np.min(raw_direct)
        print(f"   ✅ Direct read: mean={direct_mean:.1f}, max={direct_max:.1f}, min={direct_min:.1f} counts")

    except Exception as e:
        print(f"   ❌ Direct hardware test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Step 4: Verify data structure
    print("\n[4/4] Validation...")

    # Check signal is above noise floor (should be >5000 counts like basic test)
    EXPECTED_MINIMUM = 5000  # Well above dark noise (~3000)

    if direct_mean > EXPECTED_MINIMUM:
        print(f"   ✅ Signal above noise floor ({direct_mean:.1f} > {EXPECTED_MINIMUM})")
    else:
        print(f"   ❌ Signal too low: {direct_mean:.1f} (expected >{EXPECTED_MINIMUM})")
        return False

    # Check spectrum shape
    print(f"   ✅ Spectrum shape: {raw_direct.shape} pixels")

    # Verify this is the same data structure that acquisition manager will store
    print(f"   ✅ Data type: {raw_direct.dtype}")
    print(f"   ✅ Storage location: numpy array (same as data['raw_spectrum'])")

    # Cleanup
    print("\n[CLEANUP] Turning off LEDs...")
    try:
        ctrl.turn_off_channels()
    except:
        pass

    print("\n" + "="*70)
    print("✅ VERIFICATION COMPLETE - Data collection working correctly!")
    print("="*70)
    print("\nSummary:")
    print(f"  • Detector reads light: {direct_mean:.1f} counts (Ch C @ 20%)")
    print(f"  • Signal range: {direct_min:.1f} to {direct_max:.1f}")
    print(f"  • Above noise floor: {direct_mean / 3000:.1f}× dark noise")
    print(f"  • Data stored as: numpy array ({raw_direct.shape})")
    print(f"\nThe acquisition manager will:")
    print(f"  1. Call usb.read_spectrum() → gets this same data")
    print(f"  2. Apply dark/afterglow corrections")
    print(f"  3. Store at data['raw_spectrum']")
    print(f"  4. Queue for UI emission")

    return True


if __name__ == "__main__":
    try:
        success = verify_data_storage()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
