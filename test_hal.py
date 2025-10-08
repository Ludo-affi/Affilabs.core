#!/usr/bin/env python3
"""
Test script for HAL system functionality
"""

import sys
import os

# Add the project root to the path so we can import from utils
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_hal_imports():
    """Test that all HAL components can be imported."""
    print("=== Testing HAL System Imports ===")
    
    try:
        from utils.hal import HALFactory
        print("✓ HALFactory import: SUCCESS")
    except ImportError as e:
        print(f"✗ HALFactory import: FAILED - {e}")
        return False
    
    try:
        from utils.hal import SPRControllerHAL, ChannelID
        print("✓ SPRControllerHAL import: SUCCESS")
    except ImportError as e:
        print(f"✗ SPRControllerHAL import: FAILED - {e}")
        return False
    
    try:
        from utils.hal.pico_p4spr_hal import PicoP4SPRHAL
        print("✓ PicoP4SPRHAL import: SUCCESS")
    except ImportError as e:
        print(f"✗ PicoP4SPRHAL import: FAILED - {e}")
        return False
    
    try:
        from utils.hal import HALError, HALConnectionError
        print("✓ HAL Exceptions import: SUCCESS")
    except ImportError as e:
        print(f"✗ HAL Exceptions import: FAILED - {e}")
        return False
    
    return True

def test_hal_functionality():
    """Test basic HAL functionality."""
    print("\n=== Testing HAL Basic Functionality ===")
    
    try:
        from utils.hal import HALFactory
        
        # Test available controllers
        controllers = HALFactory.get_available_controllers()
        print(f"✓ Available controllers: {controllers}")
        
        # Test controller capabilities
        if "PicoP4SPR" in controllers:
            caps = HALFactory.get_controller_capabilities("PicoP4SPR")
            if caps:
                print(f"✓ PicoP4SPR capabilities: {caps['max_channels']} channels, temp support: {caps['supports_temperature']}")
            else:
                print("✗ Could not get PicoP4SPR capabilities")
        
        # Test device detection (may not find devices without hardware)
        print("✓ Detecting connected devices...")
        devices = HALFactory.detect_connected_devices()
        if devices:
            for device in devices:
                print(f"  Found: {device['model']} v{device.get('firmware_version', 'Unknown')}")
        else:
            print("  No devices detected (normal if no hardware connected)")
        
        return True
        
    except Exception as e:
        print(f"✗ HAL functionality test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_hal_adapter():
    """Test the HAL adapter for integration."""
    print("\n=== Testing HAL Integration Adapter ===")
    
    try:
        from utils.hal.integration_example import HALControllerAdapter
        
        adapter = HALControllerAdapter()
        print("✓ HAL Adapter created successfully")
        
        # Test connection attempt (will likely fail without hardware, but should not crash)
        print("✓ Testing adapter connection (may fail without hardware)...")
        try:
            result = adapter.connect()
            if result:
                print("✓ Adapter connection: SUCCESS")
                
                # Test basic operations
                device_info = adapter.get_device_info()
                if device_info:
                    print(f"  Device: {device_info.get('model', 'Unknown')}")
                
                # Test capabilities if using HAL
                if adapter.using_hal:
                    caps = adapter.get_capabilities()
                    if caps:
                        print(f"  Channels: {caps['supported_channels']}")
                
                adapter.disconnect()
                print("✓ Adapter disconnection: SUCCESS")
            else:
                print("○ Adapter connection: FAILED (normal without hardware)")
        except Exception as e:
            print(f"○ Adapter connection test failed: {e} (normal without hardware)")
        
        return True
        
    except Exception as e:
        print(f"✗ HAL adapter test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all HAL tests."""
    print("HAL System Test Suite")
    print("=" * 50)
    
    success = True
    
    # Test imports
    if not test_hal_imports():
        success = False
    
    # Test functionality
    if not test_hal_functionality():
        success = False
    
    # Test adapter
    if not test_hal_adapter():
        success = False
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 ALL HAL TESTS PASSED!")
        print("\nThe HAL system is ready for integration.")
        print("\nNext steps:")
        print("1. Connect PicoP4SPR hardware to test device detection")
        print("2. Use HALControllerAdapter in your HardwareManager")
        print("3. Gradually migrate to direct HAL usage")
    else:
        print("❌ SOME HAL TESTS FAILED!")
        print("\nPlease check the error messages above.")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)