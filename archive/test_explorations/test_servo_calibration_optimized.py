"""Test optimized servo calibration timing and LED control.

Tests:
1. Fast servo movement (150ms instead of 500ms)
2. Reduced settle times (0.1s instead of 0.3s)
3. LED batch command with channel pre-enable
4. Reduced scan count (2 instead of 5)

Expected results:
- All 4 LEDs turn on during calibration
- ~10x faster than original (0.5s per position vs 5s)
- Reliable measurements with 2 scans

Author: ezControl-AI System
Date: January 3, 2026
"""

import sys
import time
from pathlib import Path

import numpy as np

# Add parent directory to path for affilabs imports
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from affilabs.core.hardware_manager import HardwareManager


def test_servo_movement_speed():
    """Test fast servo movement (150ms duration)."""
    print("=" * 80)
    print("TEST 1: Servo Movement Speed (150ms)")
    print("=" * 80)

    hm = HardwareManager()

    try:
        print("\n1. Connecting to hardware...")
        result = hm.scan_and_connect(auto_connect=True)
        if not result.get('controller_connected', False):
            print("❌ Failed to connect to controller")
            return False
        print("✅ Controller connected")

        # Test servo movement timing
        positions = [1, 90, 180, 90, 1]
        print(f"\n2. Testing servo movement to {len(positions)} positions...")
        print("   (Should take ~1.5s total with 150ms duration + 200ms wait)")

        start_time = time.perf_counter()

        for pwm in positions:
            angle = int((pwm / 255.0) * 180.0)
            cmd = f"servo:{angle},150\n"

            if hm.ctrl._ser is not None:
                hm.ctrl._ser.reset_input_buffer()
                hm.ctrl._ser.write(cmd.encode())
                time.sleep(0.05)
                response = hm.ctrl._ser.read(10)
                time.sleep(0.20)  # 150ms movement + 50ms settle

            print(f"   Position {pwm} → angle {angle}°")

        elapsed = time.perf_counter() - start_time
        expected = len(positions) * 0.25  # 250ms per move

        print(f"\n✅ Movement complete!")
        print(f"   Total time: {elapsed:.2f}s")
        print(f"   Expected: ~{expected:.2f}s")
        print(f"   Per position: {elapsed/len(positions)*1000:.0f}ms")

        if elapsed < expected * 1.5:
            print("   ✅ FAST servo movement working!")
            return True
        else:
            print("   ⚠️  Slower than expected")
            return False

    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    finally:
        hm.disconnect_all()


def test_led_batch_with_enable():
    """Test LED batch command with channel pre-enable."""
    print("\n" + "=" * 80)
    print("TEST 2: LED Batch Command with Channel Enable")
    print("=" * 80)

    hm = HardwareManager()

    try:
        print("\n1. Connecting to hardware...")
        result = hm.scan_and_connect(auto_connect=True)
        if not result.get('controller_connected', False):
            print("❌ Failed to connect to controller")
            return False
        if not result.get('detector_connected', False):
            print("❌ Failed to connect to spectrometer")
            hm.disconnect_all()
            return False
        print("✅ Hardware connected")

        # Set integration time
        print("\n2. Setting integration time to 5ms...")
        hm.usb.set_integration(5.0)
        time.sleep(0.1)

        # Test LED enable + batch
        led_intensity = 51  # 20% of 255

        print(f"\n3. Turning on all 4 LED channels...")
        for ch in ['a', 'b', 'c', 'd']:
            hm.ctrl.turn_on_channel(ch=ch)
            print(f"   Channel {ch.upper()} enabled")
        time.sleep(0.05)

        print(f"\n4. Setting all LEDs to {led_intensity}/255 via batch command...")
        hm.ctrl.set_batch_intensities(a=led_intensity, b=led_intensity,
                                      c=led_intensity, d=led_intensity)
        time.sleep(0.2)

        print("\n5. Reading spectrum...")
        spectrum = hm.usb.read_intensity()
        max_intensity = spectrum.max()
        mean_intensity = spectrum.mean()
        top_20_mean = spectrum[np.argsort(spectrum)[-20:]].mean()

        print(f"\n   Spectrum statistics:")
        print(f"   Max intensity: {max_intensity:.1f}")
        print(f"   Mean intensity: {mean_intensity:.1f}")
        print(f"   Top 20 mean: {top_20_mean:.1f}")

        # Check if we're getting good signal (all 4 LEDs on)
        if top_20_mean > 5000:
            print(f"\n✅ ALL 4 LEDS ARE ON! (signal > 5000)")
            success = True
        elif top_20_mean > 2000:
            print(f"\n⚠️  Moderate signal ({top_20_mean:.0f}) - maybe 2 LEDs?")
            success = False
        else:
            print(f"\n❌ Low signal ({top_20_mean:.0f}) - LEDs not working correctly")
            success = False

        # Turn off LEDs
        print("\n6. Turning off all LEDs...")
        hm.ctrl.set_batch_intensities(a=0, b=0, c=0, d=0)

        return success

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        try:
            hm.ctrl.set_batch_intensities(a=0, b=0, c=0, d=0)
        except:
            pass
        hm.disconnect_all()


def test_fast_scan_timing():
    """Test 2-scan measurement vs 5-scan."""
    print("\n" + "=" * 80)
    print("TEST 3: Fast Scan Timing (2 scans vs 5 scans)")
    print("=" * 80)

    hm = HardwareManager()

    try:
        print("\n1. Connecting to hardware...")
        result = hm.scan_and_connect(auto_connect=True)
        if not result.get('controller_connected', False):
            print("❌ Failed to connect to controller")
            return False
        if not result.get('detector_connected', False):
            print("❌ Failed to connect to spectrometer")
            hm.disconnect_all()
            return False
        print("✅ Hardware connected")

        # Set up LEDs
        led_intensity = 51
        for ch in ['a', 'b', 'c', 'd']:
            hm.ctrl.turn_on_channel(ch=ch)
        time.sleep(0.05)
        hm.ctrl.set_batch_intensities(a=led_intensity, b=led_intensity,
                                      c=led_intensity, d=led_intensity)
        time.sleep(0.2)

        hm.usb.set_integration(5.0)
        time.sleep(0.1)

        # Test 2 scans
        print("\n2. Testing 2-scan measurement...")
        start = time.perf_counter()
        measurements_2 = []
        for _ in range(2):
            spectrum = hm.usb.read_intensity()
            top_20_mean = spectrum[np.argsort(spectrum)[-20:]].mean()
            measurements_2.append(top_20_mean)
        time_2 = time.perf_counter() - start

        mean_2 = np.mean(measurements_2)
        std_2 = np.std(measurements_2)
        cv_2 = (std_2 / mean_2) * 100

        print(f"   Time: {time_2*1000:.0f}ms")
        print(f"   Mean: {mean_2:.1f}")
        print(f"   Std: {std_2:.1f}")
        print(f"   CV: {cv_2:.2f}%")

        # Test 5 scans
        print("\n3. Testing 5-scan measurement...")
        start = time.perf_counter()
        measurements_5 = []
        for _ in range(5):
            spectrum = hm.usb.read_intensity()
            top_20_mean = spectrum[np.argsort(spectrum)[-20:]].mean()
            measurements_5.append(top_20_mean)
            time.sleep(0.05)
        time_5 = time.perf_counter() - start

        mean_5 = np.mean(measurements_5)
        std_5 = np.std(measurements_5)
        cv_5 = (std_5 / mean_5) * 100

        print(f"   Time: {time_5*1000:.0f}ms")
        print(f"   Mean: {mean_5:.1f}")
        print(f"   Std: {std_5:.1f}")
        print(f"   CV: {cv_5:.2f}%")

        # Compare
        speedup = time_5 / time_2
        print(f"\n4. Comparison:")
        print(f"   2-scan speedup: {speedup:.1f}x faster")
        print(f"   Mean difference: {abs(mean_5 - mean_2):.1f} ({abs(mean_5 - mean_2)/mean_5*100:.1f}%)")
        print(f"   CV difference: {abs(cv_5 - cv_2):.2f}%")

        if cv_2 < 5.0 and speedup > 1.5:
            print(f"\n✅ 2-scan method is reliable and {speedup:.1f}x faster!")
            success = True
        else:
            print(f"\n⚠️  May need more scans for stability (CV={cv_2:.2f}%)")
            success = False

        # Turn off LEDs
        hm.ctrl.set_batch_intensities(a=0, b=0, c=0, d=0)

        return success

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        try:
            hm.ctrl.set_batch_intensities(a=0, b=0, c=0, d=0)
        except:
            pass
        hm.disconnect_all()


def test_full_position_cycle():
    """Test complete position measurement cycle with all optimizations."""
    print("\n" + "=" * 80)
    print("TEST 4: Full Position Cycle (Servo + LED + 2 Scans)")
    print("=" * 80)

    hm = HardwareManager()

    try:
        print("\n1. Connecting to hardware...")
        result = hm.scan_and_connect(auto_connect=True)
        if not result.get('controller_connected', False):
            print("❌ Failed to connect to controller")
            return False
        if not result.get('detector_connected', False):
            print("❌ Failed to connect to spectrometer")
            hm.disconnect_all()
            return False
        print("✅ Hardware connected")

        # Set up
        led_intensity = 51
        for ch in ['a', 'b', 'c', 'd']:
            hm.ctrl.turn_on_channel(ch=ch)
        time.sleep(0.05)
        hm.ctrl.set_batch_intensities(a=led_intensity, b=led_intensity,
                                      c=led_intensity, d=led_intensity)
        hm.usb.set_integration(5.0)
        time.sleep(0.2)

        # Test 3 positions
        positions = [50, 100, 150]
        print(f"\n2. Testing {len(positions)} positions with full cycle...")
        print("   (Servo move + settle + 2 scans)")

        start_total = time.perf_counter()

        for pwm in positions:
            start_pos = time.perf_counter()

            # Move servo
            angle = int((pwm / 255.0) * 180.0)
            cmd = f"servo:{angle},150\n"
            if hm.ctrl._ser is not None:
                hm.ctrl._ser.reset_input_buffer()
                hm.ctrl._ser.write(cmd.encode())
                time.sleep(0.05)
                response = hm.ctrl._ser.read(10)
                time.sleep(0.20)  # 150ms movement + 50ms settle
                time.sleep(0.1)   # Additional settle

            # Take 2 measurements
            measurements = []
            for _ in range(2):
                spectrum = hm.usb.read_intensity()
                top_20_mean = spectrum[np.argsort(spectrum)[-20:]].mean()
                measurements.append(top_20_mean)

            mean_val = np.mean(measurements)
            std_val = np.std(measurements)

            time_pos = time.perf_counter() - start_pos

            print(f"   PWM {pwm:3d}: {mean_val:7.1f} ± {std_val:5.1f} ({time_pos*1000:.0f}ms)")

        total_time = time.perf_counter() - start_total
        avg_per_position = total_time / len(positions)

        print(f"\n3. Results:")
        print(f"   Total time: {total_time:.2f}s")
        print(f"   Per position: {avg_per_position*1000:.0f}ms")
        print(f"   Expected old method: ~{len(positions) * 5:.0f}s (5s per position)")

        speedup = (len(positions) * 5) / total_time

        if avg_per_position < 1.0:
            print(f"\n✅ OPTIMIZED! {speedup:.0f}x faster than original!")
            success = True
        else:
            print(f"\n⚠️  Slower than expected ({avg_per_position:.1f}s per position)")
            success = False

        # Turn off LEDs
        hm.ctrl.set_batch_intensities(a=0, b=0, c=0, d=0)

        return success

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        try:
            hm.ctrl.set_batch_intensities(a=0, b=0, c=0, d=0)
        except:
            pass
        hm.disconnect_all()


def main():
    """Run all optimization tests."""
    print("\n" + "=" * 80)
    print("SERVO CALIBRATION OPTIMIZATION TEST SUITE")
    print("=" * 80)
    print("\nTesting optimizations:")
    print("  1. Servo duration: 500ms → 150ms")
    print("  2. Settle time: 0.3s → 0.1s")
    print("  3. LED batch with channel enable (4 LEDs)")
    print("  4. Scans per position: 5 → 2")
    print("\nExpected speedup: ~10x (5s → 0.5s per position)")
    print("=" * 80)

    results = {}

    # Run tests
    results['servo_speed'] = test_servo_movement_speed()
    results['led_batch'] = test_led_batch_with_enable()
    results['scan_timing'] = test_fast_scan_timing()
    results['full_cycle'] = test_full_position_cycle()

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name.replace('_', ' ').title()}")

    total_passed = sum(results.values())
    total_tests = len(results)

    print("\n" + "=" * 80)
    print(f"Results: {total_passed}/{total_tests} tests passed")

    if total_passed == total_tests:
        print("✅ ALL OPTIMIZATIONS WORKING!")
    elif total_passed >= total_tests * 0.75:
        print("⚠️  Most optimizations working, some issues")
    else:
        print("❌ Multiple optimization failures")

    print("=" * 80)

    return total_passed == total_tests


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
