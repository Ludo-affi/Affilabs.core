"""
Hardware Manager HAL Integration Example

This shows how to integrate the HAL system into your existing HardwareManager
while maintaining backward compatibility.
"""

from typing import Any, Optional
from utils.logger import logger

# Try to import HAL system
try:
    from utils.hal import HALFactory, SPRControllerHAL, HALError, HALConnectionError, ChannelID
    from utils.hal.integration_example import HALControllerAdapter
    HAL_AVAILABLE = True
    logger.info("HAL system available - enhanced hardware support enabled")
except ImportError as e:
    logger.warning(f"HAL system not available, using legacy only: {e}")
    HAL_AVAILABLE = False


class EnhancedHardwareManager:
    """
    Enhanced HardwareManager with HAL integration.
    
    This is an example of how to integrate the HAL system into your
    existing HardwareManager class while maintaining compatibility.
    """
    
    def __init__(self) -> None:
        """Initialize enhanced hardware manager."""
        self.controller_adapter: Optional[HALControllerAdapter] = None
        self.device_config: dict[str, Any] = {"ctrl": "", "knx": ""}
        self.using_hal = False
        
    def connect_controller(self, device_type: Optional[str] = None) -> bool:
        """
        Connect to SPR controller using HAL if available.
        
        Args:
            device_type: Specific device type or None for auto-detection
            
        Returns:
            True if connection successful
        """
        if HAL_AVAILABLE:
            try:
                logger.info("Attempting HAL-based controller connection...")
                self.controller_adapter = HALControllerAdapter()
                
                if self.controller_adapter.connect(device_type=device_type):
                    self.using_hal = self.controller_adapter.using_hal
                    
                    # Update device config
                    device_info = self.controller_adapter.get_device_info()
                    self.device_config["ctrl"] = device_info.get("model", "Unknown")
                    
                    connection_type = "HAL" if self.using_hal else "Legacy"
                    logger.info(f"Controller connected via {connection_type}: {self.device_config['ctrl']}")
                    
                    # Log capabilities if using HAL
                    if self.using_hal:
                        caps = self.controller_adapter.get_capabilities()
                        if caps:
                            logger.info(f"Controller capabilities: {caps['max_channels']} channels, "
                                      f"temperature: {caps['supports_temperature']}")
                    
                    return True
                else:
                    logger.warning("Controller connection failed")
                    return False
                    
            except Exception as e:
                logger.error(f"Controller connection error: {e}")
                return False
        else:
            # Fallback to original connection method
            logger.info("Using legacy controller connection...")
            return self._connect_legacy_controller()
    
    def activate_channel(self, channel: str) -> bool:
        """
        Activate measurement channel.
        
        Args:
            channel: Channel identifier ('a', 'b', 'c', 'd')
            
        Returns:
            True if activation successful
        """
        if self.controller_adapter:
            try:
                if self.using_hal:
                    # Use HAL interface
                    channel_map = {'a': ChannelID.A, 'b': ChannelID.B, 'c': ChannelID.C, 'd': ChannelID.D}
                    hal_channel = channel_map.get(channel.lower())
                    if hal_channel and self.controller_adapter.hal_controller:
                        return self.controller_adapter.hal_controller.activate_channel(hal_channel)
                else:
                    # Use legacy interface via adapter
                    return self.controller_adapter.turn_on_channel(channel)
            except Exception as e:
                logger.error(f"Channel activation failed: {e}")
                return False
        return False
    
    def get_controller_temperature(self) -> float:
        """
        Get controller temperature.
        
        Returns:
            Temperature in Celsius, or -1 if not available
        """
        if self.controller_adapter:
            try:
                return self.controller_adapter.get_temp()
            except Exception as e:
                logger.warning(f"Temperature reading failed: {e}")
        return -1.0
    
    def get_controller_status(self) -> dict[str, Any]:
        """
        Get comprehensive controller status.
        
        Returns:
            Status dictionary with connection and capability info
        """
        if not self.controller_adapter:
            return {"connected": False, "hal_enabled": False}
        
        status = {
            "connected": self.controller_adapter.is_connected(),
            "hal_enabled": HAL_AVAILABLE,
            "using_hal": self.using_hal,
            "device_info": self.controller_adapter.get_device_info(),
        }
        
        # Add capabilities if using HAL
        if self.using_hal:
            caps = self.controller_adapter.get_capabilities()
            if caps:
                status["capabilities"] = caps
        
        return status
    
    def health_check(self) -> bool:
        """
        Perform controller health check.
        
        Returns:
            True if controller is healthy and responsive
        """
        if self.controller_adapter:
            try:
                return self.controller_adapter.health_check()
            except Exception as e:
                logger.warning(f"Health check failed: {e}")
        return False
    
    def disconnect_controller(self) -> None:
        """Disconnect from controller."""
        if self.controller_adapter:
            try:
                self.controller_adapter.disconnect()
                logger.info("Controller disconnected")
            except Exception as e:
                logger.warning(f"Disconnect error: {e}")
            finally:
                self.controller_adapter = None
                self.using_hal = False
                self.device_config["ctrl"] = ""
    
    def _connect_legacy_controller(self) -> bool:
        """Fallback legacy controller connection."""
        # This would contain your original controller connection logic
        # For now, just return False to indicate no legacy connection available
        logger.warning("Legacy controller connection not implemented in this example")
        return False
    
    def get_hal_info(self) -> dict[str, Any]:
        """
        Get information about HAL system availability and status.
        
        Returns:
            Dictionary with HAL system information
        """
        info = {
            "hal_available": HAL_AVAILABLE,
            "using_hal": self.using_hal,
        }
        
        if HAL_AVAILABLE:
            info["available_controllers"] = HALFactory.get_available_controllers()
            info["connected_devices"] = HALFactory.detect_connected_devices()
        
        return info


def demonstrate_enhanced_hardware_manager():
    """Demonstrate the enhanced hardware manager."""
    print("=== Enhanced Hardware Manager Demo ===\n")
    
    # Create enhanced hardware manager
    hw_mgr = EnhancedHardwareManager()
    
    # Show HAL system info
    hal_info = hw_mgr.get_hal_info()
    print(f"HAL Available: {hal_info['hal_available']}")
    if hal_info['hal_available']:
        print(f"Available Controllers: {hal_info['available_controllers']}")
        if hal_info['connected_devices']:
            print("Connected Devices:")
            for device in hal_info['connected_devices']:
                print(f"  - {device['model']} v{device.get('firmware_version', 'Unknown')}")
        else:
            print("No devices currently connected")
    print()
    
    # Attempt controller connection
    print("Attempting controller connection...")
    if hw_mgr.connect_controller():
        print("✓ Controller connection successful")
        
        # Show status
        status = hw_mgr.get_controller_status()
        print(f"  Device: {status['device_info'].get('model', 'Unknown')}")
        print(f"  Using HAL: {status['using_hal']}")
        
        # Test capabilities
        if status.get('capabilities'):
            caps = status['capabilities']
            print(f"  Channels: {caps['supported_channels']}")
            print(f"  Temperature Support: {caps['supports_temperature']}")
        
        # Test basic operations
        print("\nTesting basic operations...")
        
        # Channel activation
        for ch in ['a', 'b']:
            result = hw_mgr.activate_channel(ch)
            print(f"  Channel {ch}: {'OK' if result else 'FAIL'}")
        
        # Temperature reading
        temp = hw_mgr.get_controller_temperature()
        if temp > -1:
            print(f"  Temperature: {temp:.1f}°C")
        else:
            print("  Temperature: Not available")
        
        # Health check
        health = hw_mgr.health_check()
        print(f"  Health Check: {'PASS' if health else 'FAIL'}")
        
        # Disconnect
        hw_mgr.disconnect_controller()
        print("\n✓ Controller disconnected")
        
    else:
        print("✗ Controller connection failed (normal without hardware)")
    
    print("\n=== Demo Complete ===")


if __name__ == "__main__":
    demonstrate_enhanced_hardware_manager()