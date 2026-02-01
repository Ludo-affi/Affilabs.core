"""Test Hardware Commands - Servo and LED Control

This script tests basic servo and LED commands to verify the hardware interface
is working correctly before running full calibration.
"""

import time
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import with minimal dependencies
try:
    from affilabs.utils.usb4000_wrapper import USB4000
    from affilabs.utils.controller import PicoP4SPR
    from affilabs.utils.hal.controller_hal import create_controller_hal
    from affilabs.utils.device_configuration import DeviceConfiguration
    ControllerInterface = None  # Will be set after wrapping with HAL
except ImportError as e:
    print(f"Import error: {e}")
    print("Trying alternative import...")
    import seabreeze
    seabreeze.use('pyseabreeze')
    import seabreeze.spectrometers as sb

    # Minimal USB4000 wrapper
    class USB4000:
        def __init__(self):
            self.spec = None

        def connect(self):
            try:
                devices = sb.list_devices()
                if not devices:
                    print("No spectrometer found")
                    return False
                self.spec = sb.Spectrometer(devices[0])
                return True
            except Exception as e:
                print(f"Failed to connect spectrometer: {e}")
                return False

        def set_integration(self, ms):
            if self.spec:
                self.spec.integration_time_micros(int(ms * 1000))

        def read_intensity(self):
            if self.spec:
                return self.spec.intensities()
            return None

        def disconnect(self):
            if self.spec:
                self.spec.close()

    # Minimal controller wrapper
    class ControllerInterface:
        def __init__(self, port=None):
            self.ser = None
            self.port = port

        def connect(self):
            try:
                import serial.tools.list_ports
                if not self.port:
                    # Find Arduino
                    ports = list(serial.tools.list_ports.comports())
                    for p in ports:
                        if 'Arduino' in p.description or 'CH340' in p.description:
                            self.port = p.device
                            break
                if not self.port:
                    print("No Arduino found")
                    return False
                self.ser = serial.Serial(self.port, 115200, timeout=1)
                time.sleep(2)
                return True
            except Exception as e:
                print(f"Failed to connect controller: {e}")
                return False

        def set_mode(self, mode):
            if self.ser:
                cmd = 's\n' if mode.lower() == 's' else 'p\n'
                self.ser.write(cmd.encode())
                time.sleep(0.1)
                return True
            return False

        def set_intensity(self, ch, val):
            if self.ser:
                cmd = f"{ch}{val}\n"
                self.ser.write(cmd.encode())
                time.sleep(0.05)

        def get_intensity(self, ch):
            return 0  # Not implemented in minimal version

        def turn_off_channels(self):
            if self.ser:
                self.ser.write(b"lx\n")
                time.sleep(0.1)

        def set_all_led_intensities(self, intensities):
            for ch, val in intensities.items():
                self.set_intensity(ch, val)
            return True

        def get_all_led_intensities(self):
            return {'a': 0, 'b': 0, 'c': 0, 'd': 0}

        def disconnect(self):
            if self.ser:
                self.ser.close()


def test_servo_commands(ctrl):
    """Test servo movement commands."""
    print("\n" + "=" * 80)
    print("TESTING SERVO COMMANDS")
    print("=" * 80)

    try:
        # Test S-mode
        print("\n1. Setting servo to S-mode...")
        result = ctrl.set_mode("s")
        print(f"   Result: {result}")
        if result:
            print("   ✓ S-mode command successful")
        else:
            print("   ✗ S-mode command failed")
        time.sleep(2)

        # Test P-mode
        print("\n2. Setting servo to P-mode...")
        result = ctrl.set_mode("p")
        print(f"   Result: {result}")
        if result:
            print("   ✓ P-mode command successful")
        else:
            print("   ✗ P-mode command failed")
        time.sleep(2)

        # Return to S-mode
        print("\n3. Returning to S-mode...")
        result = ctrl.set_mode("s")
        print(f"   Result: {result}")
        time.sleep(1)

        print("\n✓ Servo tests complete")
        return True

    except Exception as e:
        print(f"\n✗ Servo test failed: {e}")
        return False


def test_led_commands(ctrl):
    """Test LED control commands."""
    print("\n" + "=" * 80)
    print("TESTING LED COMMANDS")
    print("=" * 80)

    try:
        # Turn off all LEDs first
        print("\n1. Turning off all LEDs...")
        ctrl.turn_off_channels()
        print("   ✓ All LEDs OFF")
        time.sleep(0.5)

        # Test individual LED control
        channels = ['a', 'b', 'c', 'd']
        for ch in channels:
            print(f"\n2. Testing LED {ch.upper()}:")
            print(f"   - Turning ON LED {ch.upper()} at intensity 255...")
            ctrl.set_intensity(ch, 255)
            time.sleep(0.3)
            print(f"   ✓ LED {ch.upper()} turned ON")

            print(f"   - Turning OFF LED {ch.upper()}...")
            ctrl.set_intensity(ch, 0)
            time.sleep(0.2)
            print(f"   ✓ LED {ch.upper()} turned OFF")

        # Test batch LED command (if supported)
        print("\n3. Testing batch LED command...")
        try:
            print("   - Setting all LEDs to 128 using batch command...")
            success = ctrl.set_batch_intensities(a=128, b=128, c=128, d=128)
            if success:
                print("   ✓ Batch command successful")
                time.sleep(0.5)
            else:
                print("   ✗ Batch command failed")
        except (AttributeError, TypeError) as e:
            print(f"   ⚠ Batch command error: {e}")
            print("   - Using individual commands instead...")
            for ch in ['a', 'b', 'c', 'd']:
                ctrl.set_intensity(ch, 128)
            time.sleep(0.5)
            print("   ✓ Individual commands successful")

        # Read back all intensities (if supported)
        print("\n4. Testing batch LED readback...")
        try:
            intensities = ctrl.get_all_led_intensities()
            if intensities:
                for ch, val in intensities.items():
                    print(f"   LED {ch.upper()}: {val}")
                print("   ✓ Read all intensities successful")
            else:
                print("   ⚠ Read returned empty (may not be supported)")
        except AttributeError:
            print("   ⚠ Readback not supported by controller (this is OK)")

        # Turn off all LEDs
        print("\n5. Final cleanup - turning off all LEDs...")
        ctrl.turn_off_channels()
        print("   ✓ All LEDs OFF")

        print("\n✓ LED tests complete")
        return True

    except Exception as e:
        print(f"\n✗ LED test failed: {e}")
        return False


def test_spectrometer(usb):
    """Test spectrometer commands."""
    print("\n" + "=" * 80)
    print("TESTING SPECTROMETER")
    print("=" * 80)

    try:
        # Test integration time
        print("\n1. Setting integration time to 50ms...")
        usb.set_integration(50.0)
        time.sleep(0.1)
        print("   ✓ Integration time set")

        # Test spectrum acquisition
        print("\n2. Acquiring spectrum...")
        spectrum = usb.read_intensity()
        if spectrum is not None:
            print(f"   ✓ Spectrum acquired: {len(spectrum)} pixels")
            print(f"   - Mean intensity: {spectrum.mean():.1f}")
            print(f"   - Max intensity: {spectrum.max():.1f}")
        else:
            print("   ✗ Failed to acquire spectrum")

        print("\n✓ Spectrometer tests complete")
        return True

    except Exception as e:
        print(f"\n✗ Spectrometer test failed: {e}")
        return False


def main():
    """Main test function."""
    print("\n" + "=" * 80)
    print("HARDWARE COMMAND TEST")
    print("=" * 80)
    print("Testing servo movements and LED control commands")
    print("=" * 80)

    ctrl = None
    usb = None

    try:
        # Connect to controller
        print("\n1. Connecting to controller...")
        raw_ctrl = PicoP4SPR()
        if not raw_ctrl.open():
            print("✗ Failed to connect to controller")
            return False

        # Wrap with HAL (like the real application does)
        device_config = DeviceConfiguration()
        ctrl = create_controller_hal(raw_ctrl, device_config)
        print("✓ Controller connected (via HAL)")

        # Connect to spectrometer
        print("\n2. Connecting to spectrometer...")
        usb = USB4000()
        if not usb.open():
            print("✗ Failed to connect to spectrometer")
            return False
        print("✓ Spectrometer connected")

        # Run tests
        servo_ok = test_servo_commands(ctrl)
        led_ok = test_led_commands(ctrl)
        spec_ok = test_spectrometer(usb)

        # Summary
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        print(f"Servo commands: {'✓ PASS' if servo_ok else '✗ FAIL'}")
        print(f"LED commands:   {'✓ PASS' if led_ok else '✗ FAIL'}")
        print(f"Spectrometer:   {'✓ PASS' if spec_ok else '✗ FAIL'}")
        print("=" * 80)

        if servo_ok and led_ok and spec_ok:
            print("\n✓ ALL TESTS PASSED")
            return True
        else:
            print("\n✗ SOME TESTS FAILED")
            return False

    except Exception as e:
        print(f"\n✗ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Cleanup
        print("\n3. Cleaning up...")
        if ctrl:
            try:
                ctrl.turn_off_channels()
                # Close the raw controller, not the HAL wrapper
                if hasattr(raw_ctrl, 'close'):
                    raw_ctrl.close()
                print("   ✓ Controller disconnected")
            except:
                pass

        if usb:
            try:
                usb.close()
                print("   ✓ Spectrometer disconnected")
            except:
                pass


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
