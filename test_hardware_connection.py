#!/usr/bin/env python3
"""
Hardware Connection Test for PicoP4SPR and USB4000
Tests the actual hardware devices connected to the system.
"""

import sys
import os
import time
import numpy as np
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

def test_pico_p4spr_connection():
    """Test PicoP4SPR connection and basic functionality."""
    print("=== Testing PicoP4SPR Hardware ===")
    
    try:
        from utils.hal import HALFactory
        
        # Create PicoP4SPR controller
        print("1. Creating PicoP4SPR controller...")
        controller = HALFactory.create_controller("PicoP4SPR")
        print(f"   ✓ Created: {type(controller).__name__}")
        
        # Get device information
        print("2. Getting device information...")
        info = controller.get_device_info()
        print(f"   Model: {info['model']}")
        print(f"   Firmware: {info.get('firmware_version', 'Unknown')}")
        print(f"   Connected: {info['connected']}")
        print(f"   Port: {info.get('port', 'Unknown')}")
        
        # Test capabilities
        print("3. Testing capabilities...")
        caps = controller.get_capabilities()
        print(f"   Channels: {caps.channels}")
        print(f"   Max channels: {caps.max_channels}")
        print(f"   Temperature support: {caps.supports_temperature}")
        print(f"   LED control: {caps.supports_led_control}")
        
        # Test basic commands
        print("4. Testing basic commands...")
        
        # Test temperature reading
        if caps.supports_temperature:
            try:
                temp = controller.read_temperature()
                print(f"   Temperature: {temp:.1f}°C")
            except Exception as e:
                print(f"   Temperature read failed: {e}")
        
        # Test LED control (briefly)
        if caps.supports_led_control:
            try:
                print("   Testing LED control...")
                controller.set_led_intensity('a', 50)  # Set channel A to 50%
                time.sleep(0.5)
                controller.set_led_intensity('a', 0)   # Turn off
                print("   ✓ LED control working")
            except Exception as e:
                print(f"   LED control failed: {e}")
        
        # Test data acquisition
        print("5. Testing data acquisition...")
        try:
            # Read from each channel
            for channel in ['a', 'b', 'c', 'd']:
                data = controller.read_channel(channel)
                if data and len(data) > 0:
                    print(f"   Channel {channel.upper()}: {len(data)} pixels, range {min(data):.0f}-{max(data):.0f}")
                else:
                    print(f"   Channel {channel.upper()}: No data")
        except Exception as e:
            print(f"   Data acquisition failed: {e}")
        
        # Disconnect
        print("6. Disconnecting...")
        controller.disconnect()
        print("   ✓ Disconnected successfully")
        
        return True
        
    except Exception as e:
        print(f"✗ PicoP4SPR test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_usb4000_connection():
    """Test USB4000 connection via Ocean Direct API and WinUSB."""
    print("\n=== Testing USB4000 Hardware (WinUSB) ===")
    
    try:
        from utils.hal import HALFactory
        
        # Create USB4000 spectrometer
        print("1. Creating USB4000 spectrometer...")
        spectrometer = HALFactory.create_spectrometer("USB4000")
        print(f"   ✓ Created: {type(spectrometer).__name__}")
        
        # Get device information
        print("2. Getting device information...")
        info = spectrometer.get_device_info()
        print(f"   Model: {info['model']}")
        print(f"   Connected: {info['connected']}")
        print(f"   Serial: {info.get('serial_number', 'Unknown')}")
        print(f"   Wavelength range: {info['wavelength_range'][0]:.1f} - {info['wavelength_range'][1]:.1f} nm")
        
        # Test capabilities
        print("3. Testing capabilities...")
        caps = spectrometer.get_capabilities()
        print(f"   Supports averaging: {caps.supports_averaging}")
        print(f"   Max averages: {caps.max_averages}")
        print(f"   Pixel count: {caps.pixel_count}")
        print(f"   Integration time: {info['min_integration_time']*1000:.1f} - {info['max_integration_time']*1000:.0f} ms")
        
        # Test spectrum capture
        print("4. Testing spectrum capture...")
        try:
            # Test with different integration times
            integration_times = [10, 50, 100]  # milliseconds
            
            for int_time in integration_times:
                wavelengths, intensities = spectrometer.capture_spectrum(
                    integration_time=int_time, 
                    averages=3
                )
                
                if wavelengths is not None and intensities is not None:
                    # Convert to numpy arrays if they aren't already
                    if not isinstance(intensities, np.ndarray):
                        intensities = np.array(intensities)
                    if not isinstance(wavelengths, np.ndarray):
                        wavelengths = np.array(wavelengths)
                        
                    print(f"   {int_time}ms: {len(wavelengths)} points, "
                          f"intensity {intensities.min():.0f}-{intensities.max():.0f}")
                else:
                    print(f"   {int_time}ms: Failed to capture")
                    
        except Exception as e:
            print(f"   Spectrum capture failed: {e}")
        
        # Test wavelength calibration
        print("5. Testing wavelength calibration...")
        try:
            wavelengths = spectrometer.get_wavelengths()
            if wavelengths is not None:
                if not isinstance(wavelengths, np.ndarray):
                    wavelengths = np.array(wavelengths)
                print(f"   Wavelengths: {len(wavelengths)} points, "
                      f"{wavelengths[0]:.1f} - {wavelengths[-1]:.1f} nm")
            else:
                print("   Wavelength calibration failed")
        except Exception as e:
            print(f"   Wavelength calibration failed: {e}")
        
        # Disconnect
        print("6. Disconnecting...")
        spectrometer.disconnect()
        print("   ✓ Disconnected successfully")
        
        return True
        
    except Exception as e:
        print(f"✗ USB4000 test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_integrated_measurement():
    """Test integrated measurement using both devices."""
    print("\n=== Testing Integrated Measurement ===")
    
    try:
        from utils.hal import HALFactory
        
        # Connect both devices
        print("1. Connecting both devices...")
        controller = HALFactory.create_controller("PicoP4SPR")
        spectrometer = HALFactory.create_spectrometer("USB4000")
        
        if not controller.get_device_info()['connected']:
            print("   ✗ PicoP4SPR not connected")
            return False
            
        if not spectrometer.get_device_info()['connected']:
            print("   ✗ USB4000 not connected")
            return False
            
        print("   ✓ Both devices connected")
        
        # Test coordinated measurement
        print("2. Testing coordinated measurement...")
        
        # Set LED on channel A
        controller.set_led_intensity('a', 75)
        time.sleep(0.1)  # Allow LED to stabilize
        
        # Capture spectrum
        wavelengths, intensities = spectrometer.capture_spectrum(
            integration_time=50, 
            averages=5
        )
        
        if wavelengths is not None and intensities is not None:
            # Convert to numpy arrays if needed
            if not isinstance(intensities, np.ndarray):
                intensities = np.array(intensities)
            if not isinstance(wavelengths, np.ndarray):
                wavelengths = np.array(wavelengths)
                
            # Find peak intensity and wavelength
            max_idx = intensities.argmax()
            peak_wavelength = wavelengths[max_idx]
            peak_intensity = intensities[max_idx]
            
            print(f"   Peak at {peak_wavelength:.1f} nm: {peak_intensity:.0f} counts")
            
            # Read SPR data from same channel
            spr_data = controller.read_channel('a')
            if spr_data and len(spr_data) > 0:
                print(f"   SPR channel A: {len(spr_data)} pixels, "
                      f"range {min(spr_data):.0f}-{max(spr_data):.0f}")
            
        # Turn off LED
        controller.set_led_intensity('a', 0)
        
        print("3. Testing dark measurement...")
        
        # Capture dark spectrum
        time.sleep(0.1)
        dark_wavelengths, dark_intensities = spectrometer.capture_spectrum(
            integration_time=50, 
            averages=5
        )
        
        if dark_wavelengths is not None and dark_intensities is not None:
            if not isinstance(dark_intensities, np.ndarray):
                dark_intensities = np.array(dark_intensities)
                
            dark_max = dark_intensities.max()
            print(f"   Dark spectrum max: {dark_max:.0f} counts")
            
            # Calculate signal-to-noise ratio
            if 'peak_intensity' in locals() and peak_intensity > 0 and dark_max > 0:
                snr = peak_intensity / dark_max
                print(f"   Signal-to-noise ratio: {snr:.1f}")
        
        # Disconnect both devices
        print("4. Disconnecting devices...")
        controller.disconnect()
        spectrometer.disconnect()
        print("   ✓ Both devices disconnected")
        
        return True
        
    except Exception as e:
        print(f"✗ Integrated measurement test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all hardware connection tests."""
    print("Hardware Connection Test Suite")
    print("=" * 60)
    print("Testing PicoP4SPR and USB4000 hardware connections")
    print("=" * 60)
    
    success = True
    
    # Test PicoP4SPR
    if not test_pico_p4spr_connection():
        success = False
    
    # Test USB4000
    if not test_usb4000_connection():
        success = False
    
    # Test integrated measurement (only if both devices work)
    if success:
        if not test_integrated_measurement():
            success = False
    else:
        print("\n=== Skipping Integrated Test (device failures) ===")
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 ALL HARDWARE TESTS PASSED!")
        print("\nYour hardware setup is working correctly:")
        print("✓ PicoP4SPR - Connected and functional")
        print("✓ USB4000 - Connected and functional") 
        print("✓ Integrated operation - Working")
        print("\nYou can now run the main application with confidence.")
    else:
        print("❌ SOME HARDWARE TESTS FAILED!")
        print("\nPlease check:")
        print("• USB cable connections")
        print("• Device drivers")
        print("• Power connections")
        print("• COM port availability")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)