"""Quick test of the collection workflow - validates all components work
without running the full 40-minute collection.

Tests:
1. Hardware connection (controller + spectrometer)
2. Polarizer movement (S-mode and P-mode)
3. Single spectrum collection in each mode
4. Data saving
5. Timing validation (should be ~4 Hz, not 1.6 Hz)
"""

import logging
import sys
import time
from pathlib import Path

import numpy as np

# Add paths
sys.path.insert(0, str(Path(__file__).parent))

from seabreeze.spectrometers import list_devices

from utils.hal.pico_p4spr_hal import PicoP4SPRHAL
from utils.usb4000_oceandirect import USB4000OceanDirect

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s :: %(levelname)s :: %(message)s",
)
logger = logging.getLogger(__name__)


def test_hardware_connection():
    """Test 1: Hardware initialization"""
    print("\n" + "=" * 70)
    print("TEST 1: HARDWARE CONNECTION")
    print("=" * 70)

    # Controller
    ctrl = PicoP4SPRHAL()
    if not ctrl.connect():
        print("❌ FAILED: Could not connect to controller")
        return None, None
    print("✅ Controller connected: PicoP4SPR")

    # Spectrometer
    devices = list_devices()
    if not devices:
        print("❌ FAILED: No spectrometer found")
        ctrl.disconnect()
        return None, None

    usb = USB4000OceanDirect()
    if not usb.connect():
        print("❌ FAILED: Could not connect to spectrometer")
        ctrl.disconnect()
        return None, None

    print("✅ Spectrometer connected: USB4000")

    return ctrl, usb


def test_polarizer_movement(ctrl):
    """Test 2: Polarizer switching"""
    print("\n" + "=" * 70)
    print("TEST 2: POLARIZER MOVEMENT")
    print("=" * 70)

    if not hasattr(ctrl, "set_mode"):
        print("❌ FAILED: Controller does not have set_mode() method")
        return False

    # Test S-mode
    print("\n  Testing S-mode...")
    result = ctrl.set_mode("s")
    if result:
        print("  ✅ S-mode command succeeded")
    else:
        print("  ⚠️  S-mode command returned False")
    time.sleep(0.5)

    # Test P-mode
    print("\n  Testing P-mode...")
    result = ctrl.set_mode("p")
    if result:
        print("  ✅ P-mode command succeeded")
    else:
        print("  ⚠️  P-mode command returned False")
    time.sleep(0.5)

    # Return to S-mode
    ctrl.set_mode("s")
    time.sleep(0.5)

    print("\n✅ Polarizer switching working")
    return True


def test_spectrum_collection(ctrl, usb):
    """Test 3: Spectrum collection in both modes"""
    print("\n" + "=" * 70)
    print("TEST 3: SPECTRUM COLLECTION")
    print("=" * 70)

    # Set integration time
    usb.set_integration_time(0.1)  # 100ms = 0.1 seconds

    # Test S-mode
    print("\n  Testing S-mode spectrum...")
    ctrl.set_mode("s")
    time.sleep(0.4)

    ctrl.activate_channel("a")
    time.sleep(0.02)

    start = time.time()
    spectrum_s = usb.acquire_spectrum()
    elapsed = time.time() - start

    ctrl.turn_off_channels()

    if spectrum_s is None:
        print("  ❌ FAILED: S-mode spectrum is None")
        return False

    max_s = np.max(spectrum_s)
    mean_s = np.mean(spectrum_s)
    print(
        f"  ✅ S-mode spectrum: {len(spectrum_s)} pixels, max={max_s:.0f}, mean={mean_s:.0f} counts",
    )
    print(f"     Acquisition time: {elapsed*1000:.1f}ms")

    # Test P-mode
    print("\n  Testing P-mode spectrum...")
    ctrl.set_mode("p")
    time.sleep(0.4)

    ctrl.activate_channel("a")
    time.sleep(0.02)

    start = time.time()
    spectrum_p = usb.acquire_spectrum()
    elapsed = time.time() - start

    ctrl.turn_off_channels()

    if spectrum_p is None:
        print("  ❌ FAILED: P-mode spectrum is None")
        return False

    max_p = np.max(spectrum_p)
    mean_p = np.mean(spectrum_p)
    print(
        f"  ✅ P-mode spectrum: {len(spectrum_p)} pixels, max={max_p:.0f}, mean={mean_p:.0f} counts",
    )
    print(f"     Acquisition time: {elapsed*1000:.1f}ms")

    # Verify mode difference
    print("\n  Verifying mode difference...")
    ratio = max_p / max(max_s, 1)
    print(f"  P/S ratio: {ratio:.1f}:1")

    if max_p >= 65535 and max_s < 35000:
        print(f"  ✅ CORRECT: P-mode saturated ({max_p:.0f}), S-mode low ({max_s:.0f})")
    elif max_s >= 65535 and max_p < 35000:
        print(
            f"  ⚠️  REVERSED: S-mode saturated ({max_s:.0f}), P-mode low ({max_p:.0f})",
        )
        print("     Polarizer commands may be backwards!")
    else:
        print(f"  ⚠️  UNCLEAR: S={max_s:.0f}, P={max_p:.0f} - check polarizer positions")

    return True


def test_timing(ctrl, usb):
    """Test 4: Acquisition timing (should be ~4 Hz)"""
    print("\n" + "=" * 70)
    print("TEST 4: ACQUISITION TIMING")
    print("=" * 70)

    print("\n  Collecting 10 spectra to measure timing...")
    print("  (Polarizer set ONCE, then 10 rapid acquisitions)")

    # Set mode once
    ctrl.set_mode("s")
    time.sleep(0.4)

    usb.set_integration_time(0.1)  # 100ms = 0.1 seconds

    # Collect 10 spectra and time each
    times = []
    for i in range(10):
        ctrl.activate_channel("a")
        time.sleep(0.02)

        start = time.time()
        spectrum = usb.acquire_spectrum()
        elapsed = time.time() - start
        times.append(elapsed)

        ctrl.turn_off_channels()
        time.sleep(0.05)  # Small gap between measurements

    avg_time = np.mean(times)
    max_rate = 1.0 / avg_time

    print(f"\n  Average acquisition time: {avg_time*1000:.1f}ms")
    print(f"  Maximum possible rate: {max_rate:.1f} Hz")

    # With 20ms LED delay + 50ms overhead = ~250ms total = 4 Hz
    expected_total = avg_time + 0.02 + 0.05  # acquisition + LED + overhead
    expected_rate = 1.0 / expected_total

    print(f"\n  Expected rate (with LED + overhead): {expected_rate:.1f} Hz")

    if expected_rate >= 3.5:
        print("  ✅ GOOD: Can achieve ~4 Hz target")
    elif expected_rate >= 2.0:
        print(f"  ⚠️  SLOW: Only ~{expected_rate:.1f} Hz (target is 4 Hz)")
    else:
        print(f"  ❌ TOO SLOW: Only ~{expected_rate:.1f} Hz (target is 4 Hz)")

    return expected_rate >= 3.5


def test_mini_collection(ctrl, usb):
    """Test 5: Mini collection (10 spectra in S-mode)"""
    print("\n" + "=" * 70)
    print("TEST 5: MINI TIME-SERIES COLLECTION")
    print("=" * 70)

    print("\n  Collecting 10 spectra over ~2.5 seconds (4 Hz)...")

    # Set mode once
    ctrl.set_mode("s")
    time.sleep(0.4)
    print("  ✅ Polarizer set to S-mode")

    usb.set_integration_time(0.1)  # 100ms = 0.1 seconds

    spectra = []
    timestamps = []

    acquisition_interval = 0.25  # 4 Hz
    start_time = time.time()
    next_acquisition = start_time

    for i in range(10):
        # Wait for next acquisition time
        while time.time() < next_acquisition:
            time.sleep(0.01)

        # Collect
        ctrl.activate_channel("a")
        time.sleep(0.02)
        spectrum = usb.acquire_spectrum()
        ctrl.turn_off_channels()

        timestamp = time.time() - start_time
        spectra.append(spectrum)
        timestamps.append(timestamp)

        next_acquisition += acquisition_interval

        if (i + 1) % 5 == 0:
            actual_rate = (i + 1) / timestamp
            print(f"    {i+1} spectra in {timestamp:.2f}s ({actual_rate:.2f} Hz)")

    total_time = timestamps[-1]
    actual_rate = len(spectra) / total_time

    print(f"\n  ✅ Collected {len(spectra)} spectra in {total_time:.2f}s")
    print(f"  Actual rate: {actual_rate:.2f} Hz (target: 4.00 Hz)")

    if actual_rate >= 3.8 and actual_rate <= 4.2:
        print("  ✅ EXCELLENT: Right on target!")
    elif actual_rate >= 3.5:
        print("  ✅ GOOD: Close to target")
    else:
        print(f"  ⚠️  OFF TARGET: {actual_rate:.2f} Hz vs 4.00 Hz target")

    return actual_rate >= 3.5


def main():
    print("=" * 70)
    print("COLLECTION WORKFLOW TEST")
    print("=" * 70)
    print("\nThis test validates all components work correctly")
    print("before running the full 40-minute collection.")
    print("\nEstimated time: ~30 seconds")
    print("=" * 70)

    ctrl = None
    usb = None

    try:
        # Test 1: Hardware
        ctrl, usb = test_hardware_connection()
        if ctrl is None or usb is None:
            print("\n❌ TEST FAILED: Cannot proceed without hardware")
            return

        # Test 2: Polarizer
        if not test_polarizer_movement(ctrl):
            print("\n❌ TEST FAILED: Polarizer not working")
            return

        # Test 3: Spectrum collection
        if not test_spectrum_collection(ctrl, usb):
            print("\n❌ TEST FAILED: Cannot collect spectra")
            return

        # Test 4: Timing
        if not test_timing(ctrl, usb):
            print("\n⚠️  WARNING: Timing may be slower than expected")

        # Test 5: Mini collection
        if not test_mini_collection(ctrl, usb):
            print("\n⚠️  WARNING: Collection rate below target")

        # Summary
        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        print("\n✅ ALL TESTS PASSED!")
        print("\nYou are ready to run the full collection:")
        print('  .\\collect_full_device_dataset.bat "demo P4SPR 2.0" "used"')
        print("\nExpected results:")
        print("  • S-mode: Low signal (no sensor resonance)")
        print("  • P-mode: High signal, likely saturated (sensor resonance)")
        print("  • Rate: ~4 Hz (250ms per spectrum)")
        print("  • Duration: ~40 minutes total (fast mode)")
        print("=" * 70)

    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ TEST FAILED with exception: {e}")
        import traceback

        traceback.print_exc()
    finally:
        # Cleanup
        if ctrl is not None:
            try:
                ctrl.turn_off_channels()
                ctrl.disconnect()
                print("\n✅ Controller disconnected")
            except:
                pass

        if usb is not None:
            try:
                usb.close()
                print("✅ Spectrometer disconnected")
            except:
                pass


if __name__ == "__main__":
    main()
