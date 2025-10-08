"""
USB4000 HAL Integration Adapter

Provides backward compatibility adapter to integrate USB4000 HAL with existing codebase.
This adapter maintains the same interface as the original USB4000 class while using
the new HAL implementation underneath.
"""

from typing import Any, List, Optional, Union

import numpy as np

from .hal import HALFactory, SpectrometerHAL
from .hal.hal_exceptions import HALConnectionError, HALError
from .logger import logger


class USB4000Adapter:
    """
    Backward compatibility adapter for USB4000 HAL integration.
    
    This class maintains the original USB4000 interface while using the new
    HAL implementation underneath, enabling seamless integration with existing code.
    """
    
    def __init__(self, app: Any) -> None:
        """
        Initialize USB4000 adapter.
        
        Args:
            app: Application instance (for error signaling compatibility)
        """
        self.app = app
        self._hal: Optional[SpectrometerHAL] = None
        self._opened = False
        
        # Compatibility properties
        self.oceandirect = None  # Legacy property for compatibility
        self.spec = None         # Legacy property for compatibility
        self.devs = []          # Legacy property for compatibility
        self.min_integration = 0.001  # Default minimum integration time
        self.max_integration = 5.0    # Default maximum integration time
        
        logger.info("Initialized USB4000 HAL adapter")
    
    @property
    def opened(self) -> bool:
        """Check if device is opened (connected)."""
        return self._opened and self._hal is not None and self._hal.is_connected()
    
    @property
    def serial_number(self) -> str:
        """Get device serial number."""
        try:
            if self._hal and self._hal.is_connected():
                return self._hal.serial_number
            return ""
        except Exception:
            return ""
    
    def get_device_list(self) -> None:
        """
        Get list of available devices (legacy compatibility method).
        
        Updates self.devs with available device IDs for compatibility.
        """
        try:
            logger.debug('Getting USB4000 device list via HAL')
            
            # Create temporary HAL instance to get device list
            if not self._hal:
                temp_hal = USB4000HAL()
                self.devs = temp_hal.get_device_list()
            else:
                self.devs = self._hal.get_device_list()
                
            logger.debug(f"USB4000 devices available: {self.devs}")
            
        except Exception as e:
            logger.error(f"Error getting USB4000 device list: {e}")
            self.devs = []
    
    def open(self) -> bool:
        """
        Open connection to USB4000 spectrometer.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            logger.info("Opening USB4000 connection via HAL")
            
            # Create HAL instance if not exists
            if not self._hal:
                self._hal = HALFactory.create_spectrometer("USB4000", auto_detect=True)
            else:
                # Reconnect if needed
                if not self._hal.is_connected():
                    self._hal.connect()
            
            if self._hal.is_connected():
                # Update compatibility properties
                device_info = self._hal.get_device_info()
                self.min_integration = device_info.get("min_integration_time", 0.001)
                self.max_integration = device_info.get("max_integration_time", 5.0)
                self.devs = [device_info.get("device_id", "unknown")]
                
                # Legacy property assignments for compatibility
                self.spec = self._hal  # Point legacy spec property to HAL
                
                self._opened = True
                logger.info("Successfully opened USB4000 connection")
                return True
            else:
                logger.error("Failed to connect to USB4000")
                return False
                
        except (HALConnectionError, HALError) as e:
            logger.error(f"HAL error opening USB4000: {e}")
            if self.app and hasattr(self.app, 'raise_error'):
                self.app.raise_error.emit('spec')
            return False
        except Exception as e:
            logger.exception(f"Unexpected error opening USB4000: {e}")
            if self.app and hasattr(self.app, 'raise_error'):
                self.app.raise_error.emit('spec')
            return False
    
    def set_integration(self, integration: float) -> bool:
        """
        Set integration time.
        
        Args:
            integration: Integration time in seconds
            
        Returns:
            True if successful, False otherwise
        """
        if not self._hal or not self._hal.is_connected():
            logger.error("Cannot set integration time: USB4000 not connected")
            return False
        
        # Validate range
        if integration < self.min_integration or integration > self.max_integration:
            logger.error(f"Integration time {integration}s out of range "
                        f"({self.min_integration}s - {self.max_integration}s)")
            return False
        
        try:
            success = self._hal.set_integration_time(integration)
            if success:
                logger.debug(f"Set USB4000 integration time to {integration}s")
            else:
                logger.error(f"Failed to set USB4000 integration time to {integration}s")
                if self.app and hasattr(self.app, 'raise_error'):
                    self.app.raise_error.emit('spec')
            return success
            
        except Exception as e:
            logger.error(f"Error setting USB4000 integration time: {e}")
            if self.app and hasattr(self.app, 'raise_error'):
                self.app.raise_error.emit('spec')
            return False
    
    def read_wavelength(self) -> Optional[np.ndarray]:
        """
        Read wavelength calibration data.
        
        Returns:
            NumPy array of wavelength values in nanometers, or None if failed
        """
        if not self._hal or not self._hal.is_connected():
            if not self.open():
                return None
        
        try:
            wavelengths = self._hal.get_wavelengths()
            logger.debug(f"Read {len(wavelengths)} wavelength points from USB4000")
            return np.array(wavelengths)
            
        except Exception as e:
            logger.error(f"Failed to read wavelength data from USB4000: {e}")
            if self.app and hasattr(self.app, 'raise_error'):
                self.app.raise_error.emit('spec')
            return None
    
    def read_intensity(self) -> Optional[np.ndarray]:
        """
        Read spectral intensity data.
        
        Returns:
            NumPy array of intensity values, or None if failed
        """
        if not self._hal or not self._hal.is_connected():
            if not self.open():
                return None
        
        try:
            # Capture spectrum using current integration time
            wavelengths, intensities = self._hal.capture_spectrum()
            logger.debug(f"Read {len(intensities)} intensity points from USB4000")
            return np.array(intensities)
            
        except Exception as e:
            logger.error(f"Failed to read intensity data from USB4000: {e}")
            if self.app and hasattr(self.app, 'raise_error'):
                self.app.raise_error.emit('spec')
            return None
    
    def close(self) -> None:
        """Close connection to USB4000 spectrometer."""
        try:
            if self._hal:
                logger.info("Closing USB4000 connection")
                self._hal.disconnect()
                self._opened = False
                
                # Clear legacy properties
                self.spec = None
                
                logger.info("Successfully closed USB4000 connection")
                
        except Exception as e:
            logger.error(f"Error closing USB4000 connection: {e}")
    
    # Additional HAL-specific methods for advanced usage
    
    def get_hal_instance(self) -> Optional[SpectrometerHAL]:
        """
        Get direct access to HAL instance for advanced operations.
        
        Returns:
            USB4000HAL instance or None if not connected
        """
        return self._hal if self._hal and self._hal.is_connected() else None
    
    def capture_averaged_spectrum(
        self, 
        integration_time: Optional[float] = None,
        averages: int = 1
    ) -> Optional[tuple[np.ndarray, np.ndarray]]:
        """
        Capture spectrum with averaging support (HAL enhancement).
        
        Args:
            integration_time: Integration time in seconds (optional)
            averages: Number of spectra to average
            
        Returns:
            Tuple of (wavelengths, intensities) as NumPy arrays, or None if failed
        """
        if not self._hal or not self._hal.is_connected():
            if not self.open():
                return None
        
        try:
            wavelengths, intensities = self._hal.capture_spectrum(
                integration_time=integration_time,
                averages=averages
            )
            return np.array(wavelengths), np.array(intensities)
            
        except Exception as e:
            logger.error(f"Failed to capture averaged spectrum: {e}")
            if self.app and hasattr(self.app, 'raise_error'):
                self.app.raise_error.emit('spec')
            return None
    
    def get_device_info(self) -> dict:
        """
        Get comprehensive device information (HAL enhancement).
        
        Returns:
            Dictionary with device information
        """
        if self._hal:
            return self._hal.get_device_info()
        return {"connected": False}
    
    def get_capabilities(self) -> Optional[dict]:
        """
        Get device capabilities (HAL enhancement).
        
        Returns:
            Capabilities dictionary or None
        """
        if self._hal:
            capabilities = self._hal.get_capabilities()
            return {
                "wavelength_range": capabilities.wavelength_range,
                "wavelength_resolution": capabilities.wavelength_resolution,
                "integration_time_range": (capabilities.min_integration_time, capabilities.max_integration_time),
                "supports_averaging": capabilities.supports_averaging,
                "max_averages": capabilities.max_averages,
                "pixel_count": capabilities.pixel_count,
                "bit_depth": capabilities.bit_depth,
                "device_model": capabilities.device_model,
            }
        return None


# Backward compatibility alias
USB4000 = USB4000Adapter