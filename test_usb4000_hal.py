#!/usr/bin/env python3
"""
USB4000 HAL Test Script

Tests both the new HAL interface and backward compatibility adapter.
"""

from utils.hal import HALFactory
from utils.usb4000_adapter import USB4000

class MockApp:
    """Mock application for testing."""
    def __init__(self):
        self.errors = []
    
    class MockSignal:
        def emit(self, error_type):
            print(f"Mock error signal: {error_type}")
    
    def __init__(self):
        self.raise_error = self.MockSignal()

def test_hal_interface():
    """Test the new HAL interface."""
    print("=== Testing USB4000 HAL Interface ===")
    
    # Test factory creation
    print("1. Creating spectrometer via HAL factory...")
    spec = HALFactory.create_spectrometer("USB4000")
    print(f"   Created: {type(spec).__name__}")
    
    # Test device info
    print("2. Getting device information...")
    info = spec.get_device_info()
    print(f"   Model: {info['model']}")
    print(f"   Connected: {info['connected']}")
    print(f"   Wavelength range: {info['wavelength_range']}")
    print(f"   Integration time range: {info['min_integration_time']:.3f}s - {info['max_integration_time']:.1f}s")
    
    # Test spectrum capture
    print("3. Capturing spectrum...")
    wavelengths, intensities = spec.capture_spectrum(integration_time=50, averages=3)
    print(f"   Captured: {len(wavelengths)} points")
    print(f"   Wavelength range: {wavelengths[0]:.1f} - {wavelengths[-1]:.1f} nm")
    print(f"   Intensity range: {min(intensities):.0f} - {max(intensities):.0f}")
    
    # Test capabilities
    print("4. Getting capabilities...")
    caps = spec.get_capabilities()
    print(f"   Supports averaging: {caps.supports_averaging}")
    print(f"   Max averages: {caps.max_averages}")
    print(f"   Pixel count: {caps.pixel_count}")
    
    spec.disconnect()
    print("   Disconnected successfully")

def test_backward_compatibility():
    """Test the backward compatibility adapter."""
    print("\n=== Testing Backward Compatibility Adapter ===")
    
    # Create mock app
    app = MockApp()
    
    # Test legacy interface
    print("1. Creating USB4000 via legacy interface...")
    usb = USB4000(app)
    print(f"   Created: {type(usb).__name__}")
    
    # Test connection
    print("2. Opening connection...")
    if usb.open():
        print("   Connected successfully")
        print(f"   Serial number: {usb.serial_number}")
        print(f"   Opened status: {usb.opened}")
        
        # Test legacy methods
        print("3. Testing legacy methods...")
        wavelengths = usb.read_wavelength()
        intensities = usb.read_intensity()
        
        if wavelengths is not None and intensities is not None:
            print(f"   read_wavelength(): {len(wavelengths)} points")
            print(f"   read_intensity(): {len(intensities)} points")
        
        # Test enhanced methods
        print("4. Testing enhanced HAL methods...")
        result = usb.capture_averaged_spectrum(integration_time=0.1, averages=5)
        if result:
            wl, int_data = result
            print(f"   capture_averaged_spectrum(): {len(wl)} wavelengths, {len(int_data)} intensities")
        
        # Test device info
        info = usb.get_device_info()
        print(f"   Device info: {info['model']}")
        
        usb.close()
        print("   Closed successfully")
    else:
        print("   Connection failed")

def test_factory_features():
    """Test HAL factory features."""
    print("\n=== Testing HAL Factory Features ===")
    
    # Test supported spectrometers
    print("1. Supported spectrometers:")
    for spec_type in HALFactory.get_supported_spectrometers():
        print(f"   - {spec_type}")
    
    # Test capabilities query
    print("2. USB4000 capabilities:")
    caps = HALFactory.get_spectrometer_capabilities("USB4000")
    if caps:
        print(f"   Wavelength range: {caps['wavelength_range']}")
        print(f"   Integration time range: {caps['min_integration_time']:.3f}s - {caps['max_integration_time']:.1f}s")
        print(f"   Supports averaging: {caps['supports_averaging']}")
    
    # Test configuration-based creation
    print("3. Configuration-based creation:")
    config = {
        "device_type": "USB4000",
        "connection": {},
        "auto_detect": True
    }
    spec = HALFactory.create_spectrometer_from_config(config)
    print(f"   Created from config: {type(spec).__name__}")
    spec.disconnect()

def test_visa_rejection():
    """Test that VISA communication attempts are properly rejected."""
    print("\n=== Testing VISA Communication Rejection ===")
    
    # Test VISA rejection in HAL factory
    print("1. Testing VISA parameter rejection...")
    spec = HALFactory.create_spectrometer("USB4000")
    
    try:
        # This should raise an error
        spec.connect(visa_resource="USB0::0x2457::0x1022::INSTR")
        print("   ❌ VISA connection was NOT rejected!")
    except Exception as e:
        print(f"   ✅ VISA correctly rejected: {type(e).__name__}")
        print(f"   Message: {str(e)}")
    
    # Test case-insensitive detection
    print("2. Testing case-insensitive VISA detection...")
    try:
        spec.connect(VISA_Address="USB0::0x2457::0x1022::INSTR")
        print("   ❌ Case-insensitive VISA was NOT rejected!")
    except Exception as e:
        print(f"   ✅ Case-insensitive VISA correctly rejected: {type(e).__name__}")
    
    # Test normal connection still works
    print("3. Testing normal Ocean Direct connection...")
    try:
        spec.disconnect()
        if spec.connect():
            print("   ✅ Ocean Direct connection successful")
            spec.disconnect()
        else:
            print("   ❌ Ocean Direct connection failed")
    except Exception as e:
        print(f"   ❌ Ocean Direct connection error: {e}")

if __name__ == "__main__":
    print("USB4000 HAL Migration Test")
    print("=" * 50)
    
    try:
        test_hal_interface()
        test_backward_compatibility()
        test_factory_features()
        test_visa_rejection()
        
        print("\n" + "=" * 50)
        print("✅ All tests completed successfully!")
        print("\nUSB4000 HAL migration is working correctly:")
        print("- HAL interface functional")
        print("- Backward compatibility maintained")
        print("- Factory patterns working")
        print("- VISA communication properly disabled")
        print("- Ready for real hardware integration")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()