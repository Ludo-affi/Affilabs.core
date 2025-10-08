"""
USB4000 Spectrometer Hardware Abstraction Layer

Ocean Optics USB4000 implementation of SpectrometerHAL interface.
Provides standardized access to USB4000 functionality via Ocean Direct API.

IMPORTANT: Uses Ocean Direct API over WinUSB - NI-VISA communication disabled.
Ocean Optics spectrometers connect via WinUSB drivers and appear in Device Manager 
under "Universal Serial Bus devices". Legacy NI-VISA USB communication is not supported.
"""

import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    from oceandirect.OceanDirectAPI import OceanDirectAPI
    OCEANDIRECT_AVAILABLE = True
except ImportError:
    # Development environment may not have oceandirect installed
    OCEANDIRECT_AVAILABLE = False
    OceanDirectAPI = None

from .hal_exceptions import HALConnectionError, HALError, HALTimeoutError
from .spectrometer_hal import SpectrometerCapabilities, SpectrometerHAL
from ..logger import logger


class USB4000HAL(SpectrometerHAL):
    """
    Hardware Abstraction Layer for Ocean Optics USB4000 Spectrometer.
    
    Uses Ocean Direct API over WinUSB for modern, native communication.
    
    Supported Communication:
    ✅ Ocean Direct API over WinUSB (recommended, modern)
    ❌ NI-VISA USB communication (legacy, disabled)
    
    Features:
    - WinUSB-based connection management (native Ocean Optics protocol)
    - Spectral data acquisition with averaging support
    - Integration time control with microsecond precision
    - Wavelength calibration access
    - Device detection and enumeration
    
    Hardware Requirements:
    - Ocean Optics USB4000 spectrometer
    - WinUSB drivers (not VISA)
    - Ocean Direct API (oceandirect package)
    
    Note: Devices appear in Device Manager under "Universal Serial Bus devices",
    not under "VISA USB devices" or similar VISA categories.
    """
    
    # USB4000 specifications
    DEVICE_MODEL = "USB4000"
    DEFAULT_TIMEOUT = 5.0  # seconds
    INTEGRATION_TIME_FACTOR = 1000  # Convert seconds to microseconds
    
    # Ocean Direct API communication (WinUSB)
    COMMUNICATION_METHOD = "Ocean Direct API over WinUSB"
    VISA_DISABLED = True  # NI-VISA communication explicitly disabled
    USB4000_PID = 0x1022       # USB4000 product ID (example)
    
    def __init__(self, device_name: Optional[str] = None) -> None:
        """Initialize USB4000 HAL."""
        super().__init__(device_name or self.DEVICE_MODEL)
        
        # Check for oceandirect availability
        if not OCEANDIRECT_AVAILABLE:
            logger.warning(f"oceandirect package not available - {self.device_name} HAL will use mock data")
            logger.info("To use real hardware, install: pip install oceandirect")
        
        # Ocean Direct API interface
        self._ocean_api = None
        self._spec_device = None
        self._device_list: List[int] = []  # Ocean Direct uses integer device IDs
        
        # Device state
        self._connected = False
        self._selected_device_id: Optional[int] = None
        
        # Cached capabilities and calibration
        self._wavelengths: Optional[np.ndarray] = None
        self._min_integration_time: float = 0.001  # 1ms default
        self._max_integration_time: float = 5.0    # 5s default
        self._current_integration_time: float = 0.1  # 100ms default
        
        logger.info(f"Initialized {self.device_name} HAL (Ocean Direct/WinUSB only - VISA disabled)")
        
        # Log communication method for clarity
        if OCEANDIRECT_AVAILABLE:
            logger.debug(f"Communication: {self.COMMUNICATION_METHOD}")
        else:
            logger.warning("Ocean Direct API not available - using mock implementation")
        
        if self.VISA_DISABLED:
            logger.debug("NI-VISA communication explicitly disabled for Ocean Optics devices")
    
    def connect(self, device_id: Optional[int] = None, **connection_params: Any) -> bool:
        """
        Connect to USB4000 spectrometer via WinUSB.
        
        Args:
            device_id: Specific device ID to connect to (optional)
            **connection_params: Additional connection parameters
            
        Returns:
            True if connection successful, False otherwise
            
        Raises:
            HALConnectionError: If connection fails
            
        Note:
            Ocean Optics devices use WinUSB drivers and are detected through
            the Ocean Direct API, not through COM port enumeration.
        """
        if not OCEANDIRECT_AVAILABLE:
            return self._connect_mock_device()
        
        try:
            logger.info(f"Connecting to {self.device_name} via Ocean Direct API (VISA disabled)")
            
            # Validate that we're not trying to use VISA
            if 'visa' in str(connection_params).lower():
                raise HALConnectionError(
                    "NI-VISA communication is disabled for Ocean Optics devices. Use Ocean Direct API.",
                    device_info={"model": self.device_model, "supported_api": "Ocean Direct", "disabled_api": "NI-VISA"}
                )
            
            # Initialize Ocean Direct API
            self._ocean_api = OceanDirectAPI()
            
            # Discover available WinUSB devices
            logger.debug("Scanning for Ocean Optics devices via Ocean Direct API (not VISA)...")
            self._ocean_api.find_usb_devices()
            self._device_list = self._ocean_api.get_device_ids()
            
            if not self._device_list:
                raise HALConnectionError(
                    f"No {self.device_name} devices found via WinUSB",
                    device_info={
                        "model": self.device_model,
                        "available_devices": 0,
                        "connection_type": "WinUSB",
                        "note": "Check Device Manager under 'Universal Serial Bus devices'"
                    }
                )
            
            # Select device to connect to
            if device_id is not None and device_id in self._device_list:
                target_device = device_id
            else:
                target_device = self._device_list[0]  # Use first available
                if device_id is not None:
                    logger.warning(f"Requested device {device_id} not found, using {target_device}")
            
            logger.debug(f"Available WinUSB devices: {self._device_list}")
            logger.debug(f"Connecting to device ID: {target_device}")
            
            # Open WinUSB device connection
            self._spec_device = self._ocean_api.open_device(target_device)
            self._selected_device_id = target_device
            
            # Initialize device parameters
            self._initialize_device()
            
            self._connected = True
            logger.info(f"Successfully connected to {self.device_name} (WinUSB device {target_device})")
            return True
            
        except Exception as e:
            self._cleanup_connection()
            error_msg = f"Failed to connect to {self.device_name} via WinUSB: {e}"
            logger.error(error_msg)
            logger.info("Troubleshooting: Check Device Manager under 'Universal Serial Bus devices' for Ocean Optics hardware")
            raise HALConnectionError(error_msg, device_info={"model": self.device_model, "connection_type": "WinUSB"})
    
    def _connect_mock_device(self) -> bool:
        """Connect to mock device when oceandirect is not available."""
        logger.info("Connecting to mock USB4000 device (oceandirect not available)")
        
        # Simulate device detection
        self._device_list = [12345]  # Mock device ID
        self._selected_device_id = 12345
        
        # Set up mock parameters
        self._wavelengths = np.linspace(200, 1100, 3648)  # Typical USB4000 range
        self._min_integration_time = 0.001
        self._max_integration_time = 5.0
        self._current_integration_time = 0.1
        
        self._connected = True
        logger.info("Successfully connected to mock USB4000 device")
        return True
    
    def connect(self, device_id: Optional[str] = None, **connection_params: Any) -> bool:
        """
        Connect to USB4000 spectrometer.
        
        Args:
            device_id: Specific device ID to connect to (optional)
            **connection_params: Additional connection parameters
            
        Returns:
            True if connection successful, False otherwise
            
        Raises:
            HALConnectionError: If connection fails
        """
        try:
            logger.info(f"Attempting to connect to {self.device_name}")
            
            # Initialize Ocean Direct API
            self._ocean_api = OceanDirectAPI()
            
            # Discover available devices
            self._ocean_api.find_usb_devices()
            self._device_list = self._ocean_api.get_device_ids()
            
            if not self._device_list:
                raise HALConnectionError(
                    f"No {self.device_name} devices found",
                    device_info={"model": self.device_model, "available_devices": 0}
                )
            
            # Select device to connect to
            if device_id and device_id in self._device_list:
                target_device = device_id
            else:
                target_device = self._device_list[0]  # Use first available
                if device_id:
                    logger.warning(f"Requested device {device_id} not found, using {target_device}")
            
            logger.debug(f"Available devices: {self._device_list}")
            logger.debug(f"Connecting to device: {target_device}")
            
            # Open device connection
            self._spec_device = self._ocean_api.open_device(target_device)
            self._selected_device_id = target_device
            
            # Initialize device parameters
            self._initialize_device()
            
            self._connected = True
            logger.info(f"Successfully connected to {self.device_name} ({target_device})")
            return True
            
        except Exception as e:
            self._cleanup_connection()
            error_msg = f"Failed to connect to {self.device_name}: {e}"
            logger.error(error_msg)
            raise HALConnectionError(error_msg, device_info={"model": self.device_model})
    
    def disconnect(self) -> None:
        """Disconnect from USB4000 spectrometer."""
        try:
            if self._connected:
                logger.info(f"Disconnecting from {self.device_name}")
                self._cleanup_connection()
                logger.info(f"Successfully disconnected from {self.device_name}")
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
    
    def _cleanup_connection(self) -> None:
        """Clean up connection resources."""
        if self._spec_device:
            try:
                self._spec_device.close_device()
            except Exception as e:
                logger.debug(f"Error closing device: {e}")
            self._spec_device = None
        
        self._ocean_api = None
        self._connected = False
        self._selected_device_id = None
        self._wavelengths = None
    
    def _initialize_device(self) -> None:
        """Initialize device parameters after connection."""
        if not self._spec_device:
            raise HALError("Device not connected")
        
        try:
            # Get integration time limits (convert from microseconds to seconds)
            self._min_integration_time = self._spec_device.get_minimum_integration_time() / self.INTEGRATION_TIME_FACTOR
            self._max_integration_time = self._spec_device.get_maximum_integration_time() / self.INTEGRATION_TIME_FACTOR
            
            # Cache wavelength calibration
            self._wavelengths = np.array(self._spec_device.get_wavelengths())
            
            # Set default integration time
            self._current_integration_time = max(self._min_integration_time, 0.1)  # 100ms or minimum
            self.set_integration_time(self._current_integration_time)
            
            logger.debug(f"Device initialized - Integration range: {self._min_integration_time:.3f}s to {self._max_integration_time:.1f}s")
            logger.debug(f"Wavelength range: {self._wavelengths[0]:.1f}nm to {self._wavelengths[-1]:.1f}nm ({len(self._wavelengths)} pixels)")
            
        except Exception as e:
            raise HALError(f"Failed to initialize device parameters: {e}")
    
    def capture_spectrum(
        self, 
        integration_time: Optional[float] = None,
        averages: int = 1
    ) -> Tuple[List[float], List[float]]:
        """
        Capture spectrum data.
        
        Args:
            integration_time: Integration time in seconds (optional, uses current setting)
            averages: Number of spectra to average (default: 1)
            
        Returns:
            Tuple of (wavelengths, intensities)
            
        Raises:
            HALError: If capture fails
            HALConnectionError: If device not connected
        """
        if not self._connected or not self._spec_device:
            raise HALConnectionError("Device not connected")
        
        try:
            # Set integration time if specified
            if integration_time is not None:
                if not self.set_integration_time(integration_time):
                    raise HALError(f"Failed to set integration time to {integration_time}s")
            
            # Capture spectrum data
            if averages <= 1:
                # Single acquisition
                intensity_data = np.array(self._spec_device.get_formatted_spectrum())
            else:
                # Multiple acquisitions with averaging
                intensity_data = self._capture_averaged_spectrum(averages)
            
            # Get wavelength data
            wavelengths = self.get_wavelengths()
            
            logger.debug(f"Captured spectrum: {len(intensity_data)} points, integration time: {self._current_integration_time:.3f}s")
            
            return wavelengths, intensity_data.tolist()
            
        except Exception as e:
            error_msg = f"Failed to capture spectrum: {e}"
            logger.error(error_msg)
            raise HALError(error_msg)
    
    def _capture_averaged_spectrum(self, num_averages: int) -> np.ndarray:
        """Capture multiple spectra and return averaged result."""
        accumulated_data = None
        
        for i in range(num_averages):
            spectrum_data = np.array(self._spec_device.get_formatted_spectrum())
            
            if accumulated_data is None:
                accumulated_data = spectrum_data.astype(float)
            else:
                accumulated_data += spectrum_data
        
        return accumulated_data / num_averages
    
    def get_wavelengths(self) -> List[float]:
        """
        Get wavelength calibration.
        
        Returns:
            List of wavelength values in nanometers
            
        Raises:
            HALConnectionError: If device not connected
            HALError: If wavelength data unavailable
        """
        if not self._connected or not self._spec_device:
            raise HALConnectionError("Device not connected")
        
        try:
            if self._wavelengths is None:
                self._wavelengths = np.array(self._spec_device.get_wavelengths())
            
            return self._wavelengths.tolist()
            
        except Exception as e:
            error_msg = f"Failed to get wavelength data: {e}"
            logger.error(error_msg)
            raise HALError(error_msg)
    
    def set_integration_time(self, time_seconds: float) -> bool:
        """
        Set integration time.
        
        Args:
            time_seconds: Integration time in seconds
            
        Returns:
            True if successful, False if out of range or failed
        """
        if not self._connected or not self._spec_device:
            logger.error("Cannot set integration time: device not connected")
            return False
        
        # Validate range
        if time_seconds < self._min_integration_time or time_seconds > self._max_integration_time:
            logger.error(f"Integration time {time_seconds:.3f}s out of range "
                        f"({self._min_integration_time:.3f}s - {self._max_integration_time:.1f}s)")
            return False
        
        try:
            # Convert to microseconds for Ocean Direct API
            time_microseconds = int(time_seconds * self.INTEGRATION_TIME_FACTOR)
            self._spec_device.set_integration_time(time_microseconds)
            self._current_integration_time = time_seconds
            
            logger.debug(f"Set integration time to {time_seconds:.3f}s ({time_microseconds}μs)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set integration time: {e}")
            return False
    
    def get_integration_time(self) -> float:
        """Get current integration time in seconds."""
        return self._current_integration_time
    
    def get_device_info(self) -> Dict[str, Any]:
        """
        Get device information.
        
        Returns:
            Dictionary containing device information
        """
        info = {
            "model": self.device_model,
            "device_name": self.device_name,
            "connected": self._connected,
            "device_id": self._selected_device_id,
            "available_devices": len(self._device_list) if self._device_list else 0,
        }
        
        if self._connected:
            info.update({
                "serial_number": getattr(self._spec_device, 'serial_number', 'Unknown'),
                "min_integration_time": self._min_integration_time,
                "max_integration_time": self._max_integration_time,
                "current_integration_time": self._current_integration_time,
                "pixel_count": len(self._wavelengths) if self._wavelengths is not None else 0,
                "wavelength_range": (
                    float(self._wavelengths[0]), 
                    float(self._wavelengths[-1])
                ) if self._wavelengths is not None else (0, 0)
            })
        
        return info
    
    def is_connected(self) -> bool:
        """Check if device is connected."""
        return self._connected and self._spec_device is not None
    
    def get_device_list(self) -> List[str]:
        """
        Get list of available USB4000 devices.
        
        Returns:
            List of device IDs
        """
        try:
            if not self._ocean_api:
                api = OceanDirectAPI()
                api.find_usb_devices()
                return api.get_device_ids()
            else:
                self._ocean_api.find_usb_devices()
                self._device_list = self._ocean_api.get_device_ids()
                return self._device_list
        except Exception as e:
            logger.error(f"Failed to get device list: {e}")
            return []
    
    @property
    def device_model(self) -> str:
        """Get device model name."""
        return self.DEVICE_MODEL
    
    @property
    def serial_number(self) -> str:
        """Get device serial number."""
        try:
            if self._connected and self._spec_device:
                return getattr(self._spec_device, 'serial_number', 'Unknown')
            return ""
        except Exception:
            return ""
    
    def _define_capabilities(self) -> SpectrometerCapabilities:
        """Define capabilities for USB4000 spectrometer."""
        # Default capabilities (updated after connection)
        wavelength_range = (200.0, 1100.0)  # Typical USB4000 range
        pixel_count = 3648  # Typical USB4000 pixel count
        
        # Update with actual device capabilities if connected
        if self._connected and self._wavelengths is not None:
            wavelength_range = (float(self._wavelengths[0]), float(self._wavelengths[-1]))
            pixel_count = len(self._wavelengths)
        
        return SpectrometerCapabilities(
            wavelength_range=wavelength_range,
            wavelength_resolution=0.2,  # Typical USB4000 resolution
            min_integration_time=self._min_integration_time,
            max_integration_time=self._max_integration_time,
            supports_dark_current_correction=False,  # Would need additional implementation
            supports_reference_correction=False,     # Would need additional implementation
            supports_averaging=True,
            max_averages=100,
            pixel_count=pixel_count,
            bit_depth=16,  # USB4000 uses 16-bit ADC
            connection_type="USB",
            device_model=self.DEVICE_MODEL
        )