"""
Test USB4000 HAL implementation

Simple test implementation to verify HAL architecture without oceandirect dependency.
For production use, install oceandirect package.

IMPORTANT: Uses Ocean Direct API over WinUSB - NI-VISA communication disabled.
This test implementation simulates the Ocean Direct API behavior.
"""

import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .hal_exceptions import HALConnectionError, HALError, HALTimeoutError
from .spectrometer_hal import SpectrometerCapabilities, SpectrometerHAL
from ..logger import logger


class USB4000TestHAL(SpectrometerHAL):
    """
    Test implementation of USB4000 HAL for architecture validation.
    
    This class provides a mock implementation that demonstrates the HAL interface
    without requiring the oceandirect dependency. Simulates Ocean Direct API behavior.
    
    Communication Method: Simulated Ocean Direct API (VISA disabled)
    """
    
    DEVICE_MODEL = "USB4000-Test"
    COMMUNICATION_METHOD = "Simulated Ocean Direct API"
    VISA_DISABLED = True  # NI-VISA communication explicitly disabled
    
    def __init__(self, device_name: Optional[str] = None) -> None:
        """Initialize USB4000 test HAL."""
        super().__init__(device_name or self.DEVICE_MODEL)
        
        self._connected = False
        self._integration_time = 0.1  # 100ms default
        
        # Simulated device specifications
        self._min_integration = 0.001  # 1ms
        self._max_integration = 5.0    # 5s
        self._wavelengths = np.linspace(200, 1100, 3648)  # Typical USB4000 range
        
        logger.info(f"Initialized {self.device_name} test HAL (Ocean Direct simulation - VISA disabled)")
        
        if self.VISA_DISABLED:
            logger.debug("NI-VISA communication disabled - using Ocean Direct API simulation")
    
    def connect(self, **connection_params: Any) -> bool:
        """Connect to simulated USB4000 via Ocean Direct API simulation."""
        
        # Validate that we're not trying to use VISA
        if 'visa' in str(connection_params).lower():
            raise HALConnectionError(
                "NI-VISA communication is disabled for Ocean Optics devices. Use Ocean Direct API.",
                device_info={"model": self.DEVICE_MODEL, "supported_api": "Ocean Direct", "disabled_api": "NI-VISA"}
            )
        
        logger.info("Connecting to simulated USB4000 via Ocean Direct API simulation")
        self._connected = True
        return True
    
    def disconnect(self) -> None:
        """Disconnect from simulated USB4000."""
        logger.info("Disconnecting from simulated USB4000")
        self._connected = False
    
    def capture_spectrum(
        self, 
        integration_time: Optional[float] = None,
        averages: int = 1
    ) -> Tuple[List[float], List[float]]:
        """Capture simulated spectrum data."""
        if not self._connected:
            raise HALConnectionError("Device not connected")
        
        if integration_time:
            self.set_integration_time(integration_time)
        
        # Generate simulated spectrum data
        wavelengths = self.get_wavelengths()
        
        # Simple simulated spectrum with some peaks
        intensities = []
        for wl in wavelengths:
            # Base intensity with some peaks
            intensity = 1000 + 500 * np.sin(wl / 100) + 200 * np.sin(wl / 50)
            # Add some noise
            intensity += np.random.normal(0, 10)
            intensities.append(max(0, intensity))
        
        logger.debug(f"Captured simulated spectrum: {len(intensities)} points")
        return wavelengths, intensities
    
    def get_wavelengths(self) -> List[float]:
        """Get wavelength calibration."""
        return self._wavelengths.tolist()
    
    def set_integration_time(self, time_ms: float) -> bool:
        """Set integration time (parameter name matches base class)."""
        # Convert from milliseconds to seconds for internal storage
        time_seconds = time_ms / 1000.0
        
        if time_seconds < self._min_integration or time_seconds > self._max_integration:
            return False
        
        self._integration_time = time_seconds
        logger.debug(f"Set integration time to {time_seconds:.3f}s")
        return True
    
    def get_device_info(self) -> Dict[str, Any]:
        """Get device information."""
        return {
            "model": self.DEVICE_MODEL,
            "device_name": self.device_name,
            "connected": self._connected,
            "serial_number": "TEST-12345",
            "min_integration_time": self._min_integration,
            "max_integration_time": self._max_integration,
            "current_integration_time": self._integration_time,
            "pixel_count": len(self._wavelengths),
            "wavelength_range": (float(self._wavelengths[0]), float(self._wavelengths[-1]))
        }
    
    def is_connected(self) -> bool:
        """Check if device is connected."""
        return self._connected
    
    def _define_capabilities(self) -> SpectrometerCapabilities:
        """Define capabilities for test spectrometer."""
        return SpectrometerCapabilities(
            wavelength_range=(200.0, 1100.0),
            wavelength_resolution=0.2,
            min_integration_time=self._min_integration,
            max_integration_time=self._max_integration,
            supports_dark_current_correction=False,
            supports_reference_correction=False,
            supports_averaging=True,
            max_averages=100,
            pixel_count=len(self._wavelengths),
            bit_depth=16,
            connection_type="USB-Test",
            device_model=self.DEVICE_MODEL
        )