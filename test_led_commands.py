"""
Test different LED control commands to find which ones actually work
"""
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from affilabs.utils.controller import PicoP4PRO
from affilabs.utils.usb4000_wrapper import USB4000

def test_led_commands():
    """Test different LED command sequences"""

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

        print("\n" + "="*70)
        print("TESTING DIFFERENT LED OFF COMMANDS")
        print("="*70)

        # Method 1: Individual channel commands (la0, lb0, lc0, ld0)
        print("\nMethod 1: Individual la0, lb0, lc0, ld0 commands...")
        for ch in ['a', 'b', 'c', 'd']:
            cmd = f"l{ch}0\n"
            print(f"  Sending: {cmd.strip()}")
            ctrl._ser.write(cmd.encode())
            time.sleep(0.05)
            resp = ctrl._ser.read(10)
            print(f"  Response: {resp!r}")

        time.sleep(0.5)
        spectrum = usb.intensities()
        max_signal = max(spectrum)
        print(f"  Result: Max signal = {max_signal:.1f} counts")

        # Method 2: lx command (turn off all)
        print("\nMethod 2: lx command (turn off all)...")
        ctrl._ser.write(b"lx\n")
        time.sleep(0.2)
        resp = ctrl._ser.read(10)
        print(f"  Response: {resp!r}")

        time.sleep(0.5)
        spectrum = usb.intensities()
        max_signal = max(spectrum)
        print(f"  Result: Max signal = {max_signal:.1f} counts")

        # Method 3: Check current mode
        print("\nMethod 3: Query current LED mode...")
        ctrl._ser.write(b"lm?\n")
        time.sleep(0.1)
        resp = ctrl._ser.read(50)
        print(f"  Response: {resp!r}")

        # Method 4: Force manual mode THEN set to 0
        print("\nMethod 4: lm:A,B,C,D then batch:000...")
        ctrl._ser.write(b"lm:A,B,C,D\n")
        time.sleep(0.1)
        resp = ctrl._ser.read(10)
        print(f"  lm response: {resp!r}")

        ctrl._ser.write(b"batch:000,000,000,000\n")
        time.sleep(0.2)
        resp = ctrl._ser.read(10)
        print(f"  batch response: {resp!r}")

        time.sleep(0.5)
        spectrum = usb.intensities()
        max_signal = max(spectrum)
        print(f"  Result: Max signal = {max_signal:.1f} counts")

        # Method 5: Try PWM mode off
        print("\nMethod 5: Disable PWM mode...")
        ctrl._ser.write(b"lp:0\n")
        time.sleep(0.2)
        resp = ctrl._ser.read(10)
        print(f"  Response: {resp!r}")

        time.sleep(0.5)
        spectrum = usb.intensities()
        max_signal = max(spectrum)
        print(f"  Result: Max signal = {max_signal:.1f} counts")

        # Method 6: Try setting to very low value with individual commands
        print("\nMethod 6: Individual commands la5, lb5, lc5, ld5...")
        for ch in ['a', 'b', 'c', 'd']:
            cmd = f"l{ch}5\n"
            ctrl._ser.write(cmd.encode())
            time.sleep(0.05)
            resp = ctrl._ser.read(10)
            print(f"  {cmd.strip()} -> {resp!r}")

        time.sleep(0.5)
        spectrum = usb.intensities()
        max_signal = max(spectrum)
        print(f"  Result: Max signal = {max_signal:.1f} counts")

        print("\n" + "="*70)
        print("If all results show 65535 counts, the LEDs are STUCK ON")
        print("and not responding to ANY commands!")
        print("="*70)

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        try:
            # Try to turn off using ALL methods
            ctrl._ser.write(b"lx\n")
            time.sleep(0.1)
            ctrl.close()
            usb.close()
        except:
            pass

    return True

if __name__ == "__main__":
    success = test_led_commands()
    sys.exit(0 if success else 1)
