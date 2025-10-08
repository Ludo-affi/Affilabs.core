#!/usr/bin/env python3
"""
Quick Hardware Test for PicoP4SPR and USB4000
Tests both devices are properly connected and functional.
"""

import sys
import time
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

def test_hardware_connection():
    """Test both PicoP4SPR and USB4000 connections."""
    print("=== Quick Hardware Connection Test ===")
    print("Testing PicoP4SPR and USB4000 connectivity")
    print("=" * 50)
    
    success = True
    
    # Test PicoP4SPR
    print("\n1. Testing PicoP4SPR (Serial/COM)...")
    try:
        from utils.hal import HALFactory
        
        controller = HALFactory.create_controller("PicoP4SPR")
        info = controller.get_device_info()
        
        if info['connected']:
            print(f"   ✓ PicoP4SPR CONNECTED")
            print(f"   Model: {info['model']}")
            print(f"   Firmware: {info.get('firmware_version', 'Unknown')}")
            print(f"   Port: {info.get('port', 'Unknown')}")
            
            # Quick LED test
            print("   Testing LED control...")
            controller.set_led_intensity('a', 25)
            time.sleep(0.3)
            controller.set_led_intensity('a', 0)
            print("   ✓ LED control working")
            
        else:
            print("   ✗ PicoP4SPR NOT CONNECTED")
            success = False
            
        controller.disconnect()
        
    except Exception as e:
        print(f"   ✗ PicoP4SPR ERROR: {e}")
        success = False
    
    # Test USB4000
    print("\n2. Testing USB4000 (WinUSB/Ocean Direct)...")
    try:
        spectrometer = HALFactory.create_spectrometer("USB4000")
        
        if spectrometer.is_connected():
            print(f"   ✓ USB4000 CONNECTED")
            print(f"   Model: {spectrometer.device_model}")
            
            # Quick spectrum test
            print("   Testing spectrum capture...")
            wavelengths, intensities = spectrometer.capture_spectrum(
                integration_time=10,  # 10ms
                averages=1
            )
            
            if wavelengths is not None and intensities is not None:
                print(f"   ✓ Spectrum captured: {len(wavelengths)} points")
                print(f"   Wavelength range: {wavelengths[0]:.1f} - {wavelengths[-1]:.1f} nm")
                
                # Calculate some basic stats
                import numpy as np
                if not isinstance(intensities, np.ndarray):
                    intensities = np.array(intensities)
                    
                print(f"   Intensity range: {intensities.min():.0f} - {intensities.max():.0f} counts")
            else:
                print("   ✗ Spectrum capture failed")
                success = False
                
        else:
            print("   ✗ USB4000 NOT CONNECTED")
            success = False
            
        spectrometer.disconnect()
        
    except Exception as e:
        print(f"   ✗ USB4000 ERROR: {e}")
        success = False
    
    # Test integrated operation
    if success:
        print("\n3. Testing integrated operation...")
        try:
            # Reconnect both devices
            controller = HALFactory.create_controller("PicoP4SPR")
            spectrometer = HALFactory.create_spectrometer("USB4000")
            
            # Turn on LED
            controller.set_led_intensity('a', 50)
            time.sleep(0.1)  # Allow LED to stabilize
            
            # Capture spectrum with LED on
            wavelengths, intensities = spectrometer.capture_spectrum(
                integration_time=20, averages=1
            )
            
            # Turn off LED
            controller.set_led_intensity('a', 0)
            
            if wavelengths is not None and intensities is not None:
                import numpy as np
                if not isinstance(intensities, np.ndarray):
                    intensities = np.array(intensities)
                    
                peak_intensity = intensities.max()
                print(f"   ✓ LED spectrum captured: peak {peak_intensity:.0f} counts")
            else:
                print("   ✗ LED spectrum failed")
                success = False
            
            # Disconnect both
            controller.disconnect()
            spectrometer.disconnect()
            
        except Exception as e:
            print(f"   ✗ Integrated test ERROR: {e}")
            success = False
    
    # Summary
    print("\n" + "=" * 50)
    if success:
        print("🎉 HARDWARE TEST PASSED!")
        print("")
        print("Both devices are connected and working:")
        print("✓ PicoP4SPR - LED control functional")
        print("✓ USB4000 - Spectrum capture functional")
        print("✓ Integrated operation - Working together")
        print("")
        print("Your hardware is ready for the main application!")
    else:
        print("❌ HARDWARE TEST FAILED!")
        print("")
        print("Please check:")
        print("• USB cable connections")
        print("• Device drivers (PicoP4SPR needs serial, USB4000 needs WinUSB)")
        print("• COM port availability")
        print("• Device Manager for proper device recognition")
    
    return success

if __name__ == "__main__":
    success = test_hardware_connection()
    sys.exit(0 if success else 1)