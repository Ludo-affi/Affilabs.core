"""
Test the FIXED LED intensity control - using individual commands
"""
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from affilabs.utils.controller import PicoP4PRO
from affilabs.utils.usb4000_wrapper import USB4000

def test_fixed_led_control():
    """Test LED control using individual laX, lbX commands"""
    
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
        # Set integration time to 5ms
        print("\nSetting integration time to 5ms...")
        usb.set_integration(5.0)
        time.sleep(0.5)
        
        print("\n" + "="*70)
        print("FIXED LED CONTROL TEST - Using individual commands")
        print("="*70)
        
        # Test sequence using individual commands
        test_values = [0, 2, 10, 50, 100]
        
        for val in test_values:
            print(f"\nSetting all LEDs to {val}/255...")
            for ch in ['a', 'b', 'c', 'd']:
                cmd = f"l{ch}{val}\n"
                ctrl._ser.write(cmd.encode())
                time.sleep(0.02)
                resp = ctrl._ser.read(10)
            
            time.sleep(0.5)
            spectrum = usb.intensities()
            max_signal = max(spectrum)
            print(f"  Max signal: {max_signal:.1f} counts")
        
        # Analysis
        print("\n" + "="*70)
        print("Expected: Signal should increase from 0 -> 2 -> 10 -> 50 -> 100")
        print("="*70)
        
        # Cleanup - turn off LEDs
        print("\nCleaning up with lx command...")
        ctrl._ser.write(b"lx\n")
        time.sleep(0.2)
        
        spectrum = usb.intensities()
        max_signal = max(spectrum)
        print(f"After lx: Max signal = {max_signal:.1f} counts")
        print("✅ LEDs turned off")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        try:
            ctrl._ser.write(b"lx\n")
            time.sleep(0.1)
            ctrl.close()
            usb.close()
        except:
            pass
    
    return True

if __name__ == "__main__":
    success = test_fixed_led_control()
    sys.exit(0 if success else 1)
