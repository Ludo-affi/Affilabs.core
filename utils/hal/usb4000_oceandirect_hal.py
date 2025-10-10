"""USB4000 Ocean Direct HAL Implementation

Ocean Optics USB4000 implementation using the Ocean Direct API.
This provides the clean architecture with Ocean Direct API integration.

This module implements the USB4000OceanDirectHAL class that provides
hardware abstraction for Ocean Optics USB4000 spectrometers using
the modern Ocean Direct API over WinUSB drivers.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ..logger import logger
from ..usb4000_oceandirect import OCEANDIRECT_AVAILABLE, USB4000OceanDirect
from .hal_exceptions import HALConnectionError, HALError
from .spectrometer_hal import SpectrometerCapabilities, SpectrometerHAL


class USB4000OceanDirectHAL(SpectrometerHAL):
    """Hardware Abstraction Layer for Ocean Optics USB4000 using Ocean Direct API.

    This implementation uses the modern Ocean Direct API over WinUSB for
    native Ocean Optics communication without external dependencies like seabreeze.

    Features:
    - Ocean Direct API integration
    - WinUSB driver support
    - Real-time spectrum acquisition
    - Integration time control
    - Device detection and enumeration

    Hardware Requirements:
    - Ocean Optics USB4000 spectrometer
    - WinUSB drivers (not VISA)
    - oceandirect package
    """

    DEVICE_MODEL = "USB4000"
    COMMUNICATION_METHOD = "Ocean Direct API over WinUSB"

    def __init__(self, device_name: str | None = None) -> None:
        """Initialize USB4000 Ocean Direct HAL."""
        super().__init__(device_name or self.DEVICE_MODEL)

        if not OCEANDIRECT_AVAILABLE:
            logger.error("Ocean Direct API not available")
            raise HALError(
                "Ocean Direct API not available. Install with: pip install oceandirect",
            )

        # Ocean Direct device interface
        self._ocean_device: USB4000OceanDirect | None = None
        self._connected = False
        self._device_ids: list[int] = []

        # Cached capabilities
        self._wavelengths: np.Optional[ndarray] = None
        self._min_integration_time: float = 0.001  # 1ms
        self._max_integration_time: float = 5.0  # 5s
        self._current_integration_time: float = 0.1  # 100ms

        logger.info(f"Initialized {self.device_name} HAL with Ocean Direct API")

    def connect(self, device_id: int | None = None, **connection_params: Any) -> bool:
        """Connect to USB4000 spectrometer.

        Args:
            device_id: Specific device ID to connect to (optional)
            **connection_params: Additional connection parameters

        Returns:
            True if connection successful, False otherwise

        """
        try:
            logger.info(f"Connecting to {self.device_name} via Ocean Direct API...")

            # Create Ocean Direct device instance
            self._ocean_device = USB4000OceanDirect()

            # Connect to device
            if self._ocean_device.connect(device_id):
                self._connected = True

                # Cache device capabilities
                self._cache_device_capabilities()

                logger.info(f"Successfully connected to {self.device_name}")
                return True
            logger.error(f"Failed to connect to {self.device_name}")
            return False

        except Exception as e:
            error_msg = f"Connection failed: {e}"
            logger.error(error_msg)
            raise HALConnectionError(error_msg) from e

    def _cache_device_capabilities(self) -> None:
        """Cache device capabilities after connection."""
        if not self._ocean_device:
            return

        try:
            # Get device info
            device_info = self._ocean_device.get_device_info()

            # Cache integration time limits
            self._min_integration_time = device_info.get("min_integration_time", 0.001)
            self._max_integration_time = device_info.get("max_integration_time", 5.0)

            # Cache wavelength calibration
            self._wavelengths = self._ocean_device.get_wavelengths()

            logger.debug("Cached device capabilities:")
            logger.debug(
                f"  Integration time range: {self._min_integration_time:.3f}s - {self._max_integration_time:.1f}s",
            )
            if self._wavelengths is not None:
                logger.debug(
                    f"  Wavelength range: {self._wavelengths[0]:.1f}nm - {self._wavelengths[-1]:.1f}nm",
                )
                logger.debug(f"  Pixel count: {len(self._wavelengths)}")

        except Exception as e:
            logger.warning(f"Failed to cache some device capabilities: {e}")

    def disconnect(self) -> None:
        """Disconnect from USB4000 spectrometer."""
        if self._ocean_device:
            try:
                self._ocean_device.disconnect()
                logger.info(f"Disconnected from {self.device_name}")
            except Exception as e:
                logger.warning(f"Error during disconnect: {e}")

        self._ocean_device = None
        self._connected = False
        self._wavelengths = None

    def is_connected(self) -> bool:
        """Check if device is connected."""
        return self._connected and self._ocean_device is not None

    @property
    def spec(self) -> USB4000OceanDirect | None:
        """Compatibility property for legacy code that checks self.usb.spec.

        Returns:
            Ocean Direct device instance if connected, None otherwise

        """
        return self._ocean_device if self.is_connected() else None

    def get_device_list(self) -> list[str]:
        """Get list of available USB4000 devices.

        Returns:
            List of device identifiers

        """
        try:
            temp_device = USB4000OceanDirect()
            device_ids = temp_device.discover_devices()
            return [str(device_id) for device_id in device_ids]

        except Exception as e:
            logger.error(f"Device discovery failed: {e}")
            return []

    def set_integration_time(self, time_seconds: float) -> bool:
        """Set integration time.

        Args:
            time_seconds: Integration time in seconds

        Returns:
            True if successful, False otherwise

        """
        if not self.is_connected():
            logger.error("Device not connected")
            return False

        if not self._ocean_device:
            logger.error("Ocean device not available")
            return False

        try:
            # Validate integration time
            if (
                time_seconds < self._min_integration_time
                or time_seconds > self._max_integration_time
            ):
                logger.error(
                    f"Integration time {time_seconds:.3f}s out of range "
                    f"({self._min_integration_time:.3f}s - {self._max_integration_time:.1f}s)",
                )
                return False

            # Set integration time
            if self._ocean_device.set_integration_time(time_seconds):
                self._current_integration_time = time_seconds
                logger.debug(f"Set integration time to {time_seconds:.3f}s")
                return True
            logger.error("Failed to set integration time")
            return False

        except Exception as e:
            logger.error(f"Failed to set integration time: {e}")
            return False

    def get_integration_time(self) -> float:
        """Get current integration time in seconds."""
        if self._ocean_device:
            return self._ocean_device.get_integration_time()
        return self._current_integration_time

    def acquire_spectrum(self, num_averages: int = 1) -> np.ndarray | None:
        """Acquire spectrum from USB4000.

        Args:
            num_averages: Number of spectra to average (default: 1)

        Returns:
            Spectrum intensity data as numpy array, or None if acquisition fails

        """
        if not self.is_connected():
            logger.error("Device not connected")
            return None

        if not self._ocean_device:
            logger.error("Ocean device not available")
            return None

        try:
            if num_averages <= 1:
                # Single acquisition
                spectrum = self._ocean_device.acquire_spectrum()
                if spectrum is not None:
                    logger.debug(f"Acquired spectrum: {len(spectrum)} points")
                return spectrum
            # Averaged acquisition
            logger.debug(f"Acquiring {num_averages} spectra for averaging")
            spectra = []

            for i in range(num_averages):
                spectrum = self._ocean_device.acquire_spectrum()
                if spectrum is None:
                    logger.warning(f"Failed to acquire spectrum {i + 1}/{num_averages}")
                    return None
                spectra.append(spectrum)

            # Calculate average
            averaged_spectrum = np.mean(spectra, axis=0)
            logger.debug(
                f"Averaged {num_averages} spectra: {len(averaged_spectrum)} points",
            )
            return averaged_spectrum

        except Exception as e:
            logger.error(f"Spectrum acquisition failed: {e}")
            return None

    def get_wavelengths(self) -> np.ndarray | None:
        """Get wavelength calibration data.

        Returns:
            Wavelength array in nanometers, or None if not available

        """
        if self._wavelengths is not None:
            return self._wavelengths.copy()

        if self._ocean_device:
            return self._ocean_device.get_wavelengths()

        return None

    def capture_spectrum(
        self,
        integration_time: float,
        averages: int = 1,
    ) -> tuple[list[float], list[float]]:
        """Capture spectrum data.

        Args:
            integration_time: Integration time in seconds
            averages: Number of spectra to average

        Returns:
            Tuple of (wavelengths, intensities)

        """
        # Set integration time
        if not self.set_integration_time(integration_time):
            raise HALError(f"Failed to set integration time to {integration_time:.3f}s")

        # Get wavelengths
        wavelengths = self.get_wavelengths()
        if wavelengths is None:
            raise HALError("Failed to get wavelength calibration")

        # Acquire spectrum
        intensities = self.acquire_spectrum(averages)
        if intensities is None:
            raise HALError("Failed to acquire spectrum")

        return wavelengths.tolist(), intensities.tolist()

    def _define_capabilities(self) -> SpectrometerCapabilities:
        """Define capabilities for USB4000 spectrometer.

        Returns:
            Capabilities information

        """
        wavelength_range = (
            (float(self._wavelengths[0]), float(self._wavelengths[-1]))
            if self._wavelengths is not None
            else (200.0, 1100.0)  # USB4000 typical range
        )

        pixel_count = len(self._wavelengths) if self._wavelengths is not None else 3648

        return SpectrometerCapabilities(
            wavelength_range=wavelength_range,
            wavelength_resolution=0.3,  # USB4000 typical resolution in nm
            min_integration_time=self._min_integration_time,
            max_integration_time=self._max_integration_time,
            supports_dark_current_correction=True,
            supports_reference_correction=True,
            supports_averaging=True,
            max_averages=1000,
            pixel_count=pixel_count,
            bit_depth=16,  # USB4000 16-bit ADC
            connection_type=self.COMMUNICATION_METHOD,
            device_model=self.DEVICE_MODEL,
        )

    def get_capabilities(self) -> SpectrometerCapabilities:
        """Get spectrometer capabilities.

        Returns:
            Capabilities information

        """
        wavelength_range = (
            (float(self._wavelengths[0]), float(self._wavelengths[-1]))
            if self._wavelengths is not None
            else (200.0, 1100.0)  # USB4000 typical range
        )

        pixel_count = len(self._wavelengths) if self._wavelengths is not None else 3648

        return SpectrometerCapabilities(
            wavelength_range=wavelength_range,
            wavelength_resolution=0.3,  # USB4000 typical resolution in nm
            min_integration_time=self._min_integration_time,
            max_integration_time=self._max_integration_time,
            supports_dark_current_correction=True,
            supports_reference_correction=True,
            supports_averaging=True,
            max_averages=1000,
            pixel_count=pixel_count,
            bit_depth=16,  # USB4000 16-bit ADC
            connection_type=self.COMMUNICATION_METHOD,
            device_model=self.DEVICE_MODEL,
        )

    def get_device_info(self) -> dict[str, Any]:
        """Get device information.

        Returns:
            Dictionary containing device information

        """
        base_info = {
            "model": self.DEVICE_MODEL,
            "communication_method": self.COMMUNICATION_METHOD,
            "connected": self.is_connected(),
            "hal_type": "USB4000OceanDirectHAL",
        }

        if self._ocean_device:
            ocean_info = self._ocean_device.get_device_info()
            base_info.update(ocean_info)

        return base_info

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
