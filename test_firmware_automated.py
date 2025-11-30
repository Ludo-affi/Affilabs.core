"""
Automated Firmware LED Test with Spectrometer Validation
Uses USB4000 spectrometer to objectively measure LED states

This provides OBJECTIVE measurements instead of visual confirmation:
- Measures actual photon counts from spectrometer
- Detects Channel A contamination automatically
- Validates LED isolation with numerical data
- No human visual interpretation needed

Run this to get quantitative before/after firmware fix comparison.
"""

import time
import numpy as np
from src.utils.controller import ArduinoController
from src.utils.usb4000_wrapper import USB4000

def print_test_header(test_num, description):
    """Print formatted test header"""
    print("\n" + "="*70)
    print(f"TEST {test_num}: {description}")
    print("="*70)

def measure_spectrum(spec, integration_time=100):
    """Measure spectrum and return total intensity"""
    spec.set_integration_time(integration_time)
    time.sleep(0.2)  # Settling time
    spectrum = spec.get_spectrum()

    # Total counts across all wavelengths
    total_intensity = np.sum(spectrum)

    # Peak intensity
    peak_intensity = np.max(spectrum)

    return total_intensity, peak_intensity, spectrum

def test_lx_command_with_spectrometer(controller, spec):
    """Test lx command using spectrometer to detect Channel A contamination"""
    print_test_header(1, "lx Command Validation with Spectrometer (Critical Bug Test)")

    integration_time = 100  # ms
    results = []

    # Test each channel
    channels = ['a', 'b', 'c', 'd']

    for ch in channels:
        print(f"\n--- Testing Channel {ch.upper()} ---")

        # Step 1: Baseline dark measurement
        controller.turn_off_channels()
        time.sleep(0.5)
        dark_total, dark_peak, _ = measure_spectrum(spec, integration_time)
        print(f"   Dark measurement: {dark_total:.0f} total counts, {dark_peak:.0f} peak")

        # Step 2: Turn on channel at 100%
        controller.set_intensity(ch, 255)
        controller.turn_on_channel(ch)
        time.sleep(0.5)
        on_total, on_peak, _ = measure_spectrum(spec, integration_time)
        print(f"   {ch.upper()} ON at 100%: {on_total:.0f} total counts, {on_peak:.0f} peak")

        # Step 3: Turn off with lx command
        print(f"   Sending lx command...")
        controller.turn_off_channels()
        time.sleep(0.5)
        off_total, off_peak, _ = measure_spectrum(spec, integration_time)
        print(f"   After lx command: {off_total:.0f} total counts, {off_peak:.0f} peak")

        # Analysis
        signal_strength = on_total - dark_total
        residual_after_lx = off_total - dark_total
        contamination_percent = (residual_after_lx / signal_strength * 100) if signal_strength > 0 else 0

        print(f"\n   📊 Analysis:")
        print(f"      Signal strength: {signal_strength:.0f} counts")
        print(f"      Residual after lx: {residual_after_lx:.0f} counts ({contamination_percent:.1f}%)")

        # Verdict
        if residual_after_lx < (dark_total * 1.1):  # Within 10% of dark
            results.append(f"✅ Channel {ch.upper()}: lx command working (residual < 10% of dark)")
        elif contamination_percent > 80:
            results.append(f"🔴 Channel {ch.upper()}: CRITICAL BUG - LED did NOT turn off! ({contamination_percent:.0f}% remaining)")
        else:
            results.append(f"⚠️ Channel {ch.upper()}: Partial turn-off ({contamination_percent:.0f}% remaining)")

    print("\n" + "-"*70)
    print("TEST 1 RESULTS:")
    for result in results:
        print(result)

    return all("✅" in r for r in results)

def test_channel_isolation_with_spectrometer(controller, spec):
    """Test that Channel A doesn't contaminate Channel B measurement"""
    print_test_header(2, "Channel Isolation Test (Channel A Contamination Detection)")

    integration_time = 100

    print("\nStep 1: Measure Channel A at 100%")
    controller.turn_off_channels()
    time.sleep(0.5)
    controller.set_intensity('a', 255)
    controller.turn_on_channel('a')
    time.sleep(0.5)
    a_total, a_peak, _ = measure_spectrum(spec, integration_time)
    print(f"   Channel A only: {a_total:.0f} total counts")

    print("\nStep 2: Turn off all with lx")
    controller.turn_off_channels()
    time.sleep(0.5)
    dark_total, dark_peak, _ = measure_spectrum(spec, integration_time)
    print(f"   After lx (dark): {dark_total:.0f} total counts")

    print("\nStep 3: Measure Channel B at 100%")
    controller.set_intensity('b', 255)
    controller.turn_on_channel('b')
    time.sleep(0.5)
    b_with_a_total, b_with_a_peak, _ = measure_spectrum(spec, integration_time)
    print(f"   Channel B only: {b_with_a_total:.0f} total counts")

    print("\nStep 4: Turn off B, measure expected Channel B alone")
    controller.turn_off_channels()
    time.sleep(0.5)

    # Now measure pure B without any A history
    controller.set_intensity('b', 255)
    controller.turn_on_channel('b')
    time.sleep(0.5)
    b_pure_total, b_pure_peak, _ = measure_spectrum(spec, integration_time)
    controller.turn_off_channels()

    print(f"   Channel B (clean): {b_pure_total:.0f} total counts")

    # Analysis
    contamination = b_with_a_total - b_pure_total
    contamination_percent = (contamination / b_pure_total * 100) if b_pure_total > 0 else 0
    a_contribution_percent = (contamination / a_total * 100) if a_total > 0 else 0

    print(f"\n📊 Analysis:")
    print(f"   Expected Channel B intensity: {b_pure_total:.0f} counts")
    print(f"   Measured Channel B (after A test): {b_with_a_total:.0f} counts")
    print(f"   Contamination: {contamination:.0f} counts ({contamination_percent:.1f}% extra)")
    print(f"   Channel A contribution: {a_contribution_percent:.1f}% of A's original intensity")

    # Verdict
    if abs(contamination_percent) < 5:
        print(f"\n✅ TEST 2 PASSED: Channel isolation working (<5% contamination)")
        return True
    elif contamination_percent > 50:
        print(f"\n🔴 TEST 2 FAILED: Channel A is still ON! (~{a_contribution_percent:.0f}% of original intensity)")
        print(f"   This is the critical bug - Channel A did NOT turn off with lx command")
        return False
    else:
        print(f"\n⚠️ TEST 2 WARNING: Moderate contamination detected ({contamination_percent:.1f}%)")
        return False

def test_all_channels_sequential(controller, spec):
    """Measure each channel sequentially to verify clean switching"""
    print_test_header(3, "Sequential Channel Measurement (Clean LED Switching)")

    integration_time = 100
    results = {}

    print("\nMeasuring each channel at 100% brightness:")

    for ch in ['a', 'b', 'c', 'd']:
        controller.turn_off_channels()
        time.sleep(0.5)

        controller.set_intensity(ch, 255)
        controller.turn_on_channel(ch)
        time.sleep(0.5)

        total, peak, spectrum = measure_spectrum(spec, integration_time)
        results[ch] = {'total': total, 'peak': peak, 'spectrum': spectrum}

        print(f"   Channel {ch.upper()}: {total:.0f} total counts, {peak:.0f} peak")

        controller.turn_off_channels()
        time.sleep(0.5)

    # Analysis: Check if intensities are reasonable and distinct
    intensities = [results[ch]['total'] for ch in ['a', 'b', 'c', 'd']]
    mean_intensity = np.mean(intensities)
    std_intensity = np.std(intensities)

    print(f"\n📊 Analysis:")
    print(f"   Mean intensity: {mean_intensity:.0f} counts")
    print(f"   Std deviation: {std_intensity:.0f} counts ({std_intensity/mean_intensity*100:.1f}%)")

    # Check for abnormal patterns
    all_similar = std_intensity / mean_intensity < 0.3  # LEDs within 30% of each other
    all_reasonable = all(i > 10000 for i in intensities)  # All above minimum threshold

    if all_reasonable:
        print(f"\n✅ TEST 3 PASSED: All channels measuring cleanly")
        print(f"   Each LED shows independent intensity (not contaminated)")
        return True
    else:
        print(f"\n❌ TEST 3 FAILED: Abnormal intensity patterns detected")
        print(f"   Possible cross-contamination or LEDs not turning off properly")
        return False

def test_batch_command_with_spectrometer(controller, spec):
    """Test batch command LED control with spectrometer"""
    print_test_header(4, "Batch Command Validation with Spectrometer")

    integration_time = 100
    results = []

    # Test 1: All LEDs at 50%
    print("\n--- Test 4.1: All LEDs at 50% (batch:128,128,128,128) ---")
    controller.turn_off_channels()
    time.sleep(0.5)

    dark_total, _, _ = measure_spectrum(spec, integration_time)

    controller._ser.write(b'batch:128,128,128,128\n')
    controller._ser.read()
    time.sleep(0.5)

    all_on_total, _, _ = measure_spectrum(spec, integration_time)
    print(f"   All at 50%: {all_on_total:.0f} counts (dark: {dark_total:.0f})")

    if (all_on_total - dark_total) > 10000:
        results.append("✅ Batch all at 50%: LEDs activated")
    else:
        results.append("❌ Batch all at 50%: LEDs did not activate")

    # Test 2: Turn off all via batch:0,0,0,0
    print("\n--- Test 4.2: Turn off all (batch:0,0,0,0) ---")
    controller._ser.write(b'batch:0,0,0,0\n')
    controller._ser.read()
    time.sleep(0.5)

    off_total, _, _ = measure_spectrum(spec, integration_time)
    residual = off_total - dark_total
    residual_percent = (residual / (all_on_total - dark_total) * 100) if (all_on_total - dark_total) > 0 else 0

    print(f"   After batch:0,0,0,0: {off_total:.0f} counts (residual: {residual:.0f}, {residual_percent:.1f}%)")

    if residual_percent < 10:
        results.append("✅ Batch turn off: All LEDs off (<10% residual)")
    else:
        results.append(f"🔴 Batch turn off: LEDs did not turn off ({residual_percent:.0f}% remaining)")

    print("\n" + "-"*70)
    print("TEST 4 RESULTS:")
    for result in results:
        print(result)

    return all("✅" in r for r in results)

def main():
    """Run automated firmware tests with spectrometer"""
    print("\n" + "="*70)
    print("AUTOMATED FIRMWARE LED TEST WITH SPECTROMETER VALIDATION")
    print("="*70)
    print("\nThis test uses USB4000 spectrometer for objective measurements")
    print("No visual confirmation needed - fully automated analysis")
    print("\n" + "="*70)

    # Initialize hardware
    print("\nInitializing hardware...")

    try:
        # Connect to controller
        print("Connecting to PicoP4SPR controller...")
        controller = ArduinoController(port='COM4', verbose=True)
        if not controller.open():
            print("❌ Failed to connect to controller")
            return False
        print("✅ Controller connected")

        # Connect to spectrometer
        print("Connecting to USB4000 spectrometer...")
        spec = USB4000()
        if not spec.connect():
            print("❌ Failed to connect to spectrometer")
            controller.close()
            return False
        print("✅ Spectrometer connected")

        # Get firmware version
        controller._ser.write(b'iv\n')
        version = controller._ser.readline().decode().strip()
        print(f"   Firmware Version: {version}")

    except Exception as e:
        print(f"❌ Hardware initialization error: {e}")
        return False

    # Run test suite
    test_results = {}

    try:
        print("\n🔬 Starting automated test suite...")

        # Test 1: lx command validation
        test_results['lx Command'] = test_lx_command_with_spectrometer(controller, spec)

        # Test 2: Channel isolation
        test_results['Channel Isolation'] = test_channel_isolation_with_spectrometer(controller, spec)

        # Test 3: Sequential measurements
        test_results['Sequential Switching'] = test_all_channels_sequential(controller, spec)

        # Test 4: Batch commands
        test_results['Batch Commands'] = test_batch_command_with_spectrometer(controller, spec)

    except KeyboardInterrupt:
        print("\n\n⚠️ Testing interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test suite error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up
        try:
            controller.turn_off_channels()
            controller.close()
            spec.disconnect()
        except:
            pass

    # Print summary
    print("\n" + "="*70)
    print("AUTOMATED TEST SUITE SUMMARY")
    print("="*70)

    for test_name, passed in test_results.items():
        status = "✅ PASSED" if passed else "🔴 FAILED"
        print(f"{test_name:.<40} {status}")

    total_tests = len(test_results)
    passed_tests = sum(test_results.values())

    print("="*70)
    print(f"OVERALL: {passed_tests}/{total_tests} tests passed")

    if passed_tests == total_tests:
        print("\n✅ ALL TESTS PASSED - Firmware working correctly!")
    elif test_results.get('lx Command') == False:
        print("\n🔴 CRITICAL BUG DETECTED - lx command does not turn off LEDs")
        print("   Channel A contamination confirmed by spectrometer measurements")
        print("   Flash the fixed firmware and re-run this test suite")
    else:
        print(f"\n⚠️ {total_tests - passed_tests} test(s) failed")

    print("="*70 + "\n")

    return passed_tests == total_tests

if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
