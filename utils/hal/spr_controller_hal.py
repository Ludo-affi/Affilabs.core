"""
SPR Controller Hardware Abstraction Layer

Provides a unified interface for all SPR controller types, abstracting
away device-specific communication protocols and command structures.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from .hal_exceptions import HALError, HALConnectionError, HALOperationError


class ChannelID(Enum):
    """Standard channel identifiers."""
    A = "a"
    B = "b" 
    C = "c"
    D = "d"


@dataclass
class ControllerCapabilities:
    """Describes capabilities of an SPR controller."""
    
    # Channel capabilities
    supported_channels: List[ChannelID]
    max_channels: int
    
    # LED control
    supports_led_control: bool
    led_intensity_range: tuple[float, float]  # (min, max)
    led_intensity_resolution: float
    
    # Temperature monitoring
    supports_temperature: bool
    temperature_range: tuple[float, float]  # (min, max) in Celsius
    temperature_accuracy: float  # +/- degrees
    
    # Timing capabilities
    min_integration_time: float  # seconds
    max_integration_time: float  # seconds
    supports_variable_timing: bool
    
    # Communication
    connection_type: str  # "USB_SERIAL", "USB_HID", etc.
    baud_rate: Optional[int]
    
    # Identification
    device_model: str
    firmware_version_format: str  # e.g., "vX.Y.Z"
    
    # Advanced features
    supports_dark_measurement: bool
    supports_multi_scan_averaging: bool
    supports_external_trigger: bool


class ControllerStatus:
    """Current status of controller."""
    
    def __init__(self) -> None:
        self.connected: bool = False
        self.firmware_version: str = ""
        self.temperature: Optional[float] = None
        self.active_channel: Optional[ChannelID] = None
        self.led_intensity: Optional[float] = None
        self.last_error: Optional[str] = None


class SPRControllerHAL(ABC):
    """
    Hardware Abstraction Layer for SPR Controllers.
    
    Provides a unified interface for controlling SPR measurement devices,
    hiding device-specific implementation details behind a common API.
    """
    
    def __init__(self, device_name: str) -> None:
        """
        Initialize controller HAL.
        
        Args:
            device_name: Human-readable device name
        """
        self.device_name = device_name
        self.status = ControllerStatus()
        self._capabilities: Optional[ControllerCapabilities] = None
    
    # ========================================================================
    # ABSTRACT METHODS - Must be implemented by device-specific classes
    # ========================================================================
    
    @abstractmethod
    def connect(self, **connection_params: Any) -> bool:
        """
        Establish connection to the controller.
        
        Args:
            **connection_params: Device-specific connection parameters
                                (port, baud_rate, timeout, etc.)
        
        Returns:
            True if connection successful, False otherwise
            
        Raises:
            HALConnectionError: If connection fails
        """
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """
        Disconnect from the controller.
        
        Raises:
            HALError: If disconnection fails
        """
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """
        Check if controller is currently connected.
        
        Returns:
            True if connected and responsive, False otherwise
        """
        pass
    
    @abstractmethod
    def get_device_info(self) -> Dict[str, Any]:
        """
        Get device identification and version information.
        
        Returns:
            Dictionary with device information:
            {
                "model": str,
                "firmware_version": str,
                "serial_number": str,  # if available
                "hardware_revision": str,  # if available
            }
            
        Raises:
            HALOperationError: If device info cannot be retrieved
        """
        pass
    
    @abstractmethod
    def activate_channel(self, channel: ChannelID) -> bool:
        """
        Activate specified measurement channel.
        
        Args:
            channel: Channel to activate
            
        Returns:
            True if activation successful, False otherwise
            
        Raises:
            HALOperationError: If channel activation fails
        """
        pass
    
    @abstractmethod
    def get_temperature(self) -> Optional[float]:
        """
        Read controller temperature.
        
        Returns:
            Temperature in Celsius, or None if not supported/available
            
        Raises:
            HALOperationError: If temperature reading fails
        """
        pass
    
    @abstractmethod
    def set_led_intensity(self, intensity: float) -> bool:
        """
        Set LED intensity for measurements.
        
        Args:
            intensity: LED intensity (0.0 to 1.0 normalized scale)
            
        Returns:
            True if setting successful, False otherwise
            
        Raises:
            HALOperationError: If LED control fails
        """
        pass
    
    @abstractmethod
    def get_led_intensity(self) -> Optional[float]:
        """
        Get current LED intensity.
        
        Returns:
            Current LED intensity (0.0 to 1.0), or None if not available
            
        Raises:
            HALOperationError: If LED status cannot be read
        """
        pass
    
    @abstractmethod
    def reset_device(self) -> bool:
        """
        Reset the controller to default state.
        
        Returns:
            True if reset successful, False otherwise
            
        Raises:
            HALOperationError: If reset fails
        """
        pass
    
    # ========================================================================
    # CONCRETE METHODS - Common implementation for all controllers
    # ========================================================================
    
    def get_capabilities(self) -> ControllerCapabilities:
        """
        Get controller capabilities.
        
        Returns:
            ControllerCapabilities object describing device features
        """
        if self._capabilities is None:
            self._capabilities = self._define_capabilities()
        return self._capabilities
    
    def validate_channel(self, channel: ChannelID) -> bool:
        """
        Check if channel is supported by this controller.
        
        Args:
            channel: Channel to validate
            
        Returns:
            True if channel is supported, False otherwise
        """
        capabilities = self.get_capabilities()
        return channel in capabilities.supported_channels
    
    def validate_led_intensity(self, intensity: float) -> bool:
        """
        Check if LED intensity is within valid range.
        
        Args:
            intensity: Intensity to validate (0.0 to 1.0)
            
        Returns:
            True if intensity is valid, False otherwise
        """
        if not self.get_capabilities().supports_led_control:
            return False
        return 0.0 <= intensity <= 1.0
    
    def get_status(self) -> ControllerStatus:
        """
        Get current controller status.
        
        Returns:
            ControllerStatus object with current state
        """
        return self.status
    
    def health_check(self) -> bool:
        """
        Perform basic health check on the controller.
        
        Returns:
            True if controller is healthy, False otherwise
        """
        try:
            if not self.is_connected():
                return False
            
            # Try to get device info as a basic communication test
            device_info = self.get_device_info()
            return bool(device_info.get("model"))
            
        except Exception:
            return False
    
    # ========================================================================
    # ABSTRACT HELPER METHODS
    # ========================================================================
    
    @abstractmethod
    def _define_capabilities(self) -> ControllerCapabilities:
        """
        Define capabilities for this specific controller type.
        
        Returns:
            ControllerCapabilities object
        """
        pass
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def __repr__(self) -> str:
        """String representation of controller."""
        return f"{self.__class__.__name__}(device_name='{self.device_name}', connected={self.status.connected})"
    
    def __enter__(self) -> SPRControllerHAL:
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit - ensure cleanup."""
        try:
            self.disconnect()
        except Exception:
            pass  # Don't raise exceptions during cleanup