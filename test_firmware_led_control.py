"""
Comprehensive Firmware LED Control Testing Suite
Tests the PWM shutdown bug fix for all 4 channels

This script validates:
1. Individual LED on/off for each channel
2. lx command properly turns off ALL LEDs including Channel A
3. No cross-contamination between channels
4. Batch command LED control
5. Rapid command sequences
6. Controller responsiveness

Run this BEFORE compiling the firmware fix to establish baseline.
Run this AFTER flashing the fixed firmware to verify the fix works.
"""

import time
import sys
import serial

# Simple controller wrapper to avoid import issues
class SimpleController:
    def __init__(self, port='COM4', baud=115200):
        self.port = port
        self.baud = baud
        self._ser = None

    def open(self):
        try:
            self._ser = serial.Serial(self.port, self.baud, timeout=1)
            time.sleep(2)  # Wait for connection
            return True
        except Exception as e:
            print(f"Error opening port: {e}")
            return False

    def close(self):
        if self._ser:
            self._ser.close()

    def turn_off_channels(self):
        if self._ser:
            self._ser.write(b'lx\n')
            return self._ser.read(1) == b'1'

    def set_intensity(self, ch, value):
        if self._ser:
            cmd = f"b{ch}{value:03d}\n".encode()
            self._ser.write(cmd)
            return self._ser.read(1) == b'1'

    def turn_on_channel(self, ch):
        if self._ser:
            cmd = f"l{ch}\n".encode()
            self._ser.write(cmd)
            return self._ser.read(1) == b'1'

def print_test_header(test_num, description):
    """Print formatted test header"""
    print("\n" + "="*70)
    print(f"TEST {test_num}: {description}")
    print("="*70)

def visual_check(prompt):
    """Prompt user for visual LED state confirmation"""
    response = input(f"\n👁️  {prompt} (y/n): ").strip().lower()
    return response == 'y'

def test_individual_led_on_off(controller):
    """Test each LED can be turned on and off independently"""
    print_test_header(1, "Individual LED On/Off Control")

    channels = ['a', 'b', 'c', 'd']
    results = []

    for ch in channels:
        print(f"\n--- Testing Channel {ch.upper()} ---")

        # Turn off all first
        controller.turn_off_channels()
        time.sleep(0.5)

        if not visual_check(f"Are ALL LEDs OFF?"):
            results.append(f"❌ Channel {ch.upper()}: Failed to turn off all LEDs before test")
            continue

        # Turn on this channel at 50%
        controller.set_intensity(ch, 128)
        controller.turn_on_channel(ch)
        time.sleep(0.5)

        if not visual_check(f"Is ONLY Channel {ch.upper()} ON (others OFF)?"):
            results.append(f"❌ Channel {ch.upper()}: Failed to turn on exclusively")
            continue

        # Turn off this channel
        controller.turn_off_channels()
        time.sleep(0.5)

        if not visual_check(f"Is Channel {ch.upper()} now OFF?"):
            results.append(f"❌ Channel {ch.upper()}: CRITICAL - lx command failed to turn off!")
            continue

        results.append(f"✅ Channel {ch.upper()}: On/Off control working")

    print("\n" + "-"*70)
    print("TEST 1 RESULTS:")
    for result in results:
        print(result)

    return all("✅" in r for r in results)

def test_lx_after_full_brightness(controller):
    """Test lx command after setting LEDs to 100% (the critical bug scenario)"""
    print_test_header(2, "lx Command After 100% Brightness (Critical Bug Test)")

    channels = ['a', 'b', 'c', 'd']
    results = []

    for ch in channels:
        print(f"\n--- Testing Channel {ch.upper()} at 100% ---")

        # Turn off all
        controller.turn_off_channels()
        time.sleep(0.5)

        # Set to 100% and turn on
        controller.set_intensity(ch, 255)
        controller.turn_on_channel(ch)
        time.sleep(0.5)

        if not visual_check(f"Is Channel {ch.upper()} ON at full brightness?"):
            results.append(f"⚠️ Channel {ch.upper()}: Failed to turn on at 100%")
            continue

        # Turn off with lx command
        print(f"   Sending lx command...")
        controller.turn_off_channels()
        time.sleep(0.5)

        # THIS IS THE CRITICAL TEST - Channel A bug makes it stay ON here
        if not visual_check(f"Is Channel {ch.upper()} completely OFF?"):
            results.append(f"🔴 Channel {ch.upper()}: CRITICAL BUG - lx failed after 100% brightness!")
        else:
            results.append(f"✅ Channel {ch.upper()}: lx command working correctly")

    print("\n" + "-"*70)
    print("TEST 2 RESULTS:")
    for result in results:
        print(result)

    return all("✅" in r for r in results)

def test_channel_isolation(controller):
    """Test that turning on one channel doesn't affect others"""
    print_test_header(3, "Channel Isolation (No Cross-Contamination)")

    print("\nTesting if Channel A remains off when turning on Channel B...")

    # Start fresh
    controller.turn_off_channels()
    time.sleep(0.5)

    # Turn on Channel A at 100%
    controller.set_intensity('a', 255)
    controller.turn_on_channel('a')
    time.sleep(0.5)

    if not visual_check("Is Channel A ON?"):
        print("❌ TEST 3 FAILED: Could not turn on Channel A")
        return False

    # Turn off all with lx
    print("Sending lx command...")
    controller.turn_off_channels()
    time.sleep(0.5)

    if not visual_check("Is Channel A OFF?"):
        print("🔴 TEST 3 FAILED: Channel A did NOT turn off (bug present)")
        return False

    # Now turn on Channel B
    print("Turning on Channel B at 50%...")
    controller.set_intensity('b', 128)
    controller.turn_on_channel('b')
    time.sleep(0.5)

    # CRITICAL CHECK: Channel A should remain OFF
    if not visual_check("Is ONLY Channel B ON (Channel A still OFF)?"):
        print("🔴 TEST 3 FAILED: Channel A turned back on when Channel B activated!")
        print("   This is the critical bug - Channel A contamination")
        return False

    print("✅ TEST 3 PASSED: Channel isolation working correctly")
    return True

def test_batch_command(controller):
    """Test batch LED command"""
    print_test_header(4, "Batch Command LED Control")

    results = []

    # Test 1: Turn on all LEDs at 25%
    print("\n--- Test 4.1: All LEDs at 25% via batch ---")
    controller.turn_off_channels()
    time.sleep(0.5)

    controller._ser.write(b'batch:64,64,64,64\n')
    ack = controller._ser.read()
    time.sleep(0.5)

    if visual_check("Are all 4 LEDs ON at low brightness?"):
        results.append("✅ Batch command: All LEDs ON")
    else:
        results.append("❌ Batch command: Failed to turn on all LEDs")

    # Test 2: Turn off all via batch:0,0,0,0
    print("\n--- Test 4.2: Turn off all via batch:0,0,0,0 ---")
    controller._ser.write(b'batch:0,0,0,0\n')
    ack = controller._ser.read()
    time.sleep(0.5)

    if visual_check("Are ALL LEDs OFF?"):
        results.append("✅ Batch command: All LEDs OFF")
    else:
        results.append("🔴 Batch command: Failed to turn off all LEDs (bug present)")

    # Test 3: Individual control via batch
    print("\n--- Test 4.3: Individual channel via batch (A=100%, B=50%, C=25%, D=0%) ---")
    controller._ser.write(b'batch:255,128,64,0\n')
    ack = controller._ser.read()
    time.sleep(0.5)

    if visual_check("Is Channel A brightest, B medium, C dimmest, D OFF?"):
        results.append("✅ Batch command: Individual brightness levels")
    else:
        results.append("⚠️ Batch command: Brightness levels not as expected")

    # Clean up
    controller.turn_off_channels()
    time.sleep(0.5)

    print("\n" + "-"*70)
    print("TEST 4 RESULTS:")
    for result in results:
        print(result)

    return all("✅" in r for r in results)

def test_rapid_switching(controller):
    """Test rapid LED switching (stress test)"""
    print_test_header(5, "Rapid LED Switching (Controller Responsiveness)")

    print("\nExecuting rapid command sequence:")
    print("A ON → OFF → B ON → OFF → C ON → OFF → D ON → OFF")
    print("(10 cycles, ~500ms per cycle)")

    try:
        for i in range(10):
            for ch in ['a', 'b', 'c', 'd']:
                controller.set_intensity(ch, 128)
                controller.turn_on_channel(ch)
                time.sleep(0.05)
                controller.turn_off_channels()
                time.sleep(0.05)

            if i % 3 == 0:
                print(f"   Cycle {i+1}/10 complete...")

        print("\n✅ Rapid switching complete - controller remained responsive")

        # Verify all LEDs are off
        time.sleep(0.5)
        if visual_check("Are ALL LEDs OFF after rapid switching?"):
            print("✅ TEST 5 PASSED: Controller responsive, all LEDs off")
            return True
        else:
            print("❌ TEST 5 FAILED: LEDs stuck on after rapid switching")
            return False

    except Exception as e:
        print(f"🔴 TEST 5 FAILED: Controller became unresponsive - {e}")
        return False

def test_brightness_levels(controller):
    """Test various brightness levels work correctly"""
    print_test_header(6, "Brightness Level Control")

    levels = [
        (25, "10%"),
        (64, "25%"),
        (128, "50%"),
        (192, "75%"),
        (255, "100%")
    ]

    results = []

    for value, description in levels:
        print(f"\n--- Testing Channel A at {description} ---")

        controller.set_intensity('a', value)
        controller.turn_on_channel('a')
        time.sleep(0.5)

        if visual_check(f"Is Channel A at {description} brightness?"):
            results.append(f"✅ {description}: Correct brightness")
        else:
            results.append(f"⚠️ {description}: Brightness may be incorrect")

        controller.turn_off_channels()
        time.sleep(0.5)

        if not visual_check("Is Channel A OFF?"):
            results.append(f"🔴 {description}: Failed to turn off after test")
            break

    print("\n" + "-"*70)
    print("TEST 6 RESULTS:")
    for result in results:
        print(result)

    return all("✅" in r for r in results)

def main():
    """Run comprehensive firmware LED control tests"""
    print("\n" + "="*70)
    print("FIRMWARE LED CONTROL TEST SUITE - V1.2 PWM Bug Fix Validation")
    print("="*70)
    print("\nThis test suite validates the PWM shutdown bug fix.")
    print("You will be asked to visually confirm LED states throughout testing.")
    print("\nIMPORTANT:")
    print("- Run this BEFORE compiling firmware to document current bugs")
    print("- Run this AFTER flashing fixed firmware to verify the fix")
    print("\n" + "="*70)

    input("\nPress Enter to start testing...")

    # Initialize controller
    print("\nConnecting to PicoP4SPR controller...")
    try:
        controller = SimpleController(port='COM4', baud=115200)
        if not controller.open():
            print("❌ Failed to connect to controller on COM4")
            print("   Please check USB connection and COM port")
            return False

        print("✅ Controller connected successfully")

        # Get firmware version
        controller._ser.write(b'iv\n')
        version = controller._ser.readline().decode().strip()
        print(f"   Firmware Version: {version}")

        controller._ser.write(b'id\n')
        device = controller._ser.readline().decode().strip()
        print(f"   Device: {device}")

    except Exception as e:
        print(f"❌ Error connecting to controller: {e}")
        return False

    # Run test suite
    test_results = {}

    try:
        # Test 1: Individual LED on/off
        test_results['Individual Control'] = test_individual_led_on_off(controller)

        # Test 2: Critical lx bug test
        test_results['lx After 100%'] = test_lx_after_full_brightness(controller)

        # Test 3: Channel isolation
        test_results['Channel Isolation'] = test_channel_isolation(controller)

        # Test 4: Batch commands
        test_results['Batch Commands'] = test_batch_command(controller)

        # Test 5: Rapid switching
        test_results['Rapid Switching'] = test_rapid_switching(controller)

        # Test 6: Brightness levels
        test_results['Brightness Levels'] = test_brightness_levels(controller)

    except KeyboardInterrupt:
        print("\n\n⚠️ Testing interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test suite error: {e}")
    finally:
        # Clean up - turn off all LEDs
        try:
            controller.turn_off_channels()
            controller.close()
        except:
            pass

    # Print summary
    print("\n" + "="*70)
    print("TEST SUITE SUMMARY")
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
    elif test_results.get('lx After 100%') == False:
        print("\n🔴 CRITICAL BUG DETECTED - lx command does not turn off LEDs after 100% brightness")
        print("   This is the known PWM shutdown bug in V1.2 firmware")
        print("   Flash the fixed firmware and re-run this test suite")
    else:
        print(f"\n⚠️ {total_tests - passed_tests} test(s) failed")

    print("="*70 + "\n")

    return passed_tests == total_tests

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
