"""
Test if LEDs are actually turning off - diagnostic for saturation issue
"""
import time
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from affilabs.utils.controller import PicoP4PRO
from affilabs.utils.usb4000_wrapper import USB4000

def test_led_control():
    """Test if LEDs respond to intensity commands"""
    
    print("Connecting to hardware...")
    
    try:
        # Connect to controller
        ctrl = PicoP4PRO()
        if not ctrl.open():
            print("❌ Failed to open P4PRO")
            return False
        print("✅ Connected to P4PRO")
    except Exception as e:
        print(f"❌ Failed to connect to P4PRO: {e}")
        return False
    
    try:
        # Connect to spectrometer
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
        print("Setting integration time to 5ms...")
        usb.set_integration(5.0)
        time.sleep(0.5)
        
        # Test 1: ALL LEDs OFF
        print("\n" + "="*70)
        print("TEST 1: ALL LEDs OFF")
        print("="*70)
        ctrl._ser.write(b"lm:A,B,C,D\n")
        time.sleep(0.1)
        ctrl.set_batch_intensities(a=0, b=0, c=0, d=0)
        time.sleep(1.0)
        
        spectrum_off = usb.intensities()
        wavelengths = usb.wavelengths  # Property, not method
        
        # Find max signal in 350-750nm range
        valid_indices = [(i, w) for i, w in enumerate(wavelengths) if 350 <= w <= 750]
        if valid_indices:
            max_idx = max(valid_indices, key=lambda x: spectrum_off[x[0]])
            max_signal_off = spectrum_off[max_idx[0]]
            max_wave_off = max_idx[1]
            print(f"Max signal (LEDs OFF): {max_signal_off:.1f} counts at {max_wave_off:.1f}nm")
        else:
            max_signal_off = max(spectrum_off)
            print(f"Max signal (LEDs OFF): {max_signal_off:.1f} counts")
        
        # Test 2: LEDs at 1%
        print("\n" + "="*70)
        print("TEST 2: LEDs at 1% (2/255)")
        print("="*70)
        ctrl.set_batch_intensities(a=2, b=2, c=2, d=2)
        time.sleep(1.0)
        
        spectrum_1pct = usb.intensities()
        if valid_indices:
            max_idx = max(valid_indices, key=lambda x: spectrum_1pct[x[0]])
            max_signal_1pct = spectrum_1pct[max_idx[0]]
            max_wave_1pct = max_idx[1]
            print(f"Max signal (LEDs 1%): {max_signal_1pct:.1f} counts at {max_wave_1pct:.1f}nm")
        else:
            max_signal_1pct = max(spectrum_1pct)
            print(f"Max signal (LEDs 1%): {max_signal_1pct:.1f} counts")
        
        # Test 3: LEDs at 10%
        print("\n" + "="*70)
        print("TEST 3: LEDs at 10% (25/255)")
        print("="*70)
        ctrl.set_batch_intensities(a=25, b=25, c=25, d=25)
        time.sleep(1.0)
        
        spectrum_10pct = usb.intensities()
        if valid_indices:
            max_idx = max(valid_indices, key=lambda x: spectrum_10pct[x[0]])
            max_signal_10pct = spectrum_10pct[max_idx[0]]
            max_wave_10pct = max_idx[1]
            print(f"Max signal (LEDs 10%): {max_signal_10pct:.1f} counts at {max_wave_10pct:.1f}nm")
        else:
            max_signal_10pct = max(spectrum_10pct)
            print(f"Max signal (LEDs 10%): {max_signal_10pct:.1f} counts")
        
        # Analysis
        print("\n" + "="*70)
        print("ANALYSIS")
        print("="*70)
        
        if max_signal_off > 1000:
            print(f"⚠️  WARNING: High signal with LEDs OFF ({max_signal_off:.0f} counts)")
            print("   Possible causes:")
            print("   - Ambient light leaking into detector")
            print("   - LEDs not turning off")
            print("   - Detector gain misconfigured")
        else:
            print(f"✅ Background signal is low ({max_signal_off:.0f} counts)")
        
        if max_signal_1pct >= 60000:
            print(f"⚠️  WARNING: Saturated at 1% LED ({max_signal_1pct:.0f} counts)")
            print("   Possible causes:")
            print("   - LED intensity commands not working")
            print("   - Polarizer stuck at high-transmission position")
        elif max_signal_1pct > max_signal_off * 10:
            print(f"✅ LEDs responding to 1% command (signal increased {max_signal_1pct/max_signal_off:.1f}x)")
        else:
            print(f"⚠️  LEDs may not be responding properly")
        
        # Turn off LEDs
        ctrl.set_batch_intensities(a=0, b=0, c=0, d=0)
        print("\n✅ LEDs turned off")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        try:
            ctrl.close()
            usb.close()
        except:
            pass
    
    return True

if __name__ == "__main__":
    success = test_led_control()
    sys.exit(0 if success else 1)
