"""
Test LED intensity control - verify that batch commands actually change brightness
"""
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from affilabs.utils.controller import PicoP4PRO
from affilabs.utils.usb4000_wrapper import USB4000

def test_led_intensity_control():
    """Test if batch intensity commands actually work"""

    print("Connecting to hardware...")

    try:
        ctrl = PicoP4PRO()
        if not ctrl.open():
            print("❌ Failed to open P4PRO")
            return False
        print("✅ Connected to P4PRO")
    except Exception as e:
        print(f"❌ Failed to connect to P4PRO: {e}")
        return False

    try:
        usb = USB4000()
        if not usb.open():
            print("❌ Failed to open USB4000")
            ctrl.close()
            return False
        print("✅ Connected to USB4000")
    except Exception as e:
        print(f"❌ Failed to connect to USB4000: {e}")
        ctrl.close()
        return False

    try:
        # Set integration time to 10ms
        print("\nSetting integration time to 10ms...")
        usb.set_integration(10.0)
        time.sleep(0.5)

        wavelengths = usb.wavelengths

        # Test sequence
        print("\n" + "="*70)
        print("LED INTENSITY CONTROL TEST")
        print("="*70)

        # Test 1: Enable manual mode
        print("\nTest 1: Setting manual mode (lm:A,B,C,D)...")
        ctrl._ser.write(b"lm:A,B,C,D\n")
        time.sleep(0.2)
        response = ctrl._ser.read(100)
        print(f"Response: {response!r}")

        # Test 2: Set to 0
        print("\nTest 2: Setting ALL LEDs to 0...")
        ctrl._ser.write(b"batch:000,000,000,000\n")
        time.sleep(0.5)
        spectrum_0 = usb.intensities()
        max_0 = max(spectrum_0)
        print(f"Max signal at 0%: {max_0:.1f} counts")

        # Test 3: Set to 10
        print("\nTest 3: Setting ALL LEDs to 10...")
        ctrl._ser.write(b"batch:010,010,010,010\n")
        time.sleep(0.5)
        spectrum_10 = usb.intensities()
        max_10 = max(spectrum_10)
        print(f"Max signal at 10/255: {max_10:.1f} counts")

        # Test 4: Set to 50
        print("\nTest 4: Setting ALL LEDs to 50...")
        ctrl._ser.write(b"batch:050,050,050,050\n")
        time.sleep(0.5)
        spectrum_50 = usb.intensities()
        max_50 = max(spectrum_50)
        print(f"Max signal at 50/255: {max_50:.1f} counts")

        # Test 5: Set to 100
        print("\nTest 5: Setting ALL LEDs to 100...")
        ctrl._ser.write(b"batch:100,100,100,100\n")
        time.sleep(0.5)
        spectrum_100 = usb.intensities()
        max_100 = max(spectrum_100)
        print(f"Max signal at 100/255: {max_100:.1f} counts")

        # Test 6: Set to 255
        print("\nTest 6: Setting ALL LEDs to 255...")
        ctrl._ser.write(b"batch:255,255,255,255\n")
        time.sleep(0.5)
        spectrum_255 = usb.intensities()
        max_255 = max(spectrum_255)
        print(f"Max signal at 255/255: {max_255:.1f} counts")

        # Analysis
        print("\n" + "="*70)
        print("ANALYSIS")
        print("="*70)

        signals = [max_0, max_10, max_50, max_100, max_255]
        print(f"Signal progression: {signals}")

        if max_0 >= 60000:
            print("⚠️  ERROR: Signal saturated even at LED=0!")
            print("   This indicates ambient light or detector issue")
        elif all(s > 60000 for s in signals):
            print("⚠️  ERROR: All signals saturated - detector receiving too much light")
        elif max_10 == max_50 == max_100 == max_255:
            print("⚠️  ERROR: LED intensity commands have NO EFFECT")
            print("   - Check if lm: command was acknowledged")
            print("   - Verify firmware supports batch: command")
        elif max_255 > max_100 > max_50 > max_10 > max_0:
            print("✅ LED intensity control WORKING - signal increases with intensity")
        else:
            print("⚠️  WARNING: LED control partially working but inconsistent")

        # Cleanup - turn off LEDs
        print("\nCleaning up - turning off LEDs...")
        ctrl._ser.write(b"batch:000,000,000,000\n")
        time.sleep(0.2)
        print("✅ LEDs turned off")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        try:
            # CRITICAL: Always turn off LEDs
            ctrl._ser.write(b"batch:000,000,000,000\n")
            time.sleep(0.1)
            ctrl.close()
            usb.close()
        except:
            pass

    return True

if __name__ == "__main__":
    success = test_led_intensity_control()
    sys.exit(0 if success else 1)
