"""USB4000 Ocean Direct API Implementation

Clean implementation of USB4000 spectrometer control using Ocean Optics OceanDirect API.
Based on official Ocean Optics documentation and sample code.

Features:
- Device discovery and connection
- Integration time control
- Spectrum acquisition
- Wavelength calibration
- Device information retrieval

Reference:
- OceanDirect User Manual (MNL-1025)
- Ocean Optics USB4000 specifications
- OceanDirect Sample Pack
"""

import logging
import threading
import time
from typing import Any, Optional

import numpy as np

from .logger import logger

try:
    # Try SeaBreeze first (modern Ocean Optics Python library)
    from seabreeze.spectrometers import Spectrometer, list_devices

    OCEANDIRECT_AVAILABLE = True
    BACKEND_TYPE = "seabreeze"
    logger.info("Using SeaBreeze backend for Ocean Optics devices")
except ImportError:
    try:
        # Fallback to legacy OceanDirect if available
        from oceandirect.OceanDirectAPI import OceanDirectAPI

        OCEANDIRECT_AVAILABLE = True
        BACKEND_TYPE = "oceandirect"
        logger.info("Using OceanDirect backend for Ocean Optics devices")
    except ImportError:
        OCEANDIRECT_AVAILABLE = False
        BACKEND_TYPE = None
        Spectrometer = None
        list_devices = None
        OceanDirectAPI = None
        logger.warning(
            "No Ocean Optics library available - install seabreeze or oceandirect"
        )

logger = logging.getLogger(__name__)


class USB4000OceanDirect:
    """USB4000 Spectrometer using Ocean Optics OceanDirect API.

    This class provides a clean interface to USB4000 spectrometers using
    the official Ocean Optics OceanDirect API. It follows Ocean Optics
    programming guidelines and best practices.
    """

    # USB4000 Specifications
    DEVICE_MODEL = "USB4000"
    DEFAULT_INTEGRATION_TIME = 0.1  # 100ms
    MIN_INTEGRATION_TIME = 0.001  # 1ms
    MAX_INTEGRATION_TIME = 5.0  # 5s
    CONNECTION_TIMEOUT = 30.0  # 30 seconds timeout for connection

    def __init__(self):
        """Initialize USB4000 OceanDirect interface."""
        if not OCEANDIRECT_AVAILABLE:
            raise ImportError(
                "OceanDirect API not available. Install with: pip install oceandirect",
            )

        self._api: OceanDirectAPI | None = None
        self._device = None
        self._device_ids: list[int] = []
        self._connected = False
        self._current_integration_time = self.DEFAULT_INTEGRATION_TIME

        # Cached device properties
        self._wavelengths: np.Optional[ndarray] = None
        self._serial_number: str | None = None
        self._min_integration_time: float | None = None
        self._max_integration_time: float | None = None

        logger.info(f"Initialized {self.DEVICE_MODEL} OceanDirect interface")

    def _connection_with_timeout(self, target_device_id, timeout_seconds=None):
        """Attempt connection with timeout to prevent indefinite hanging.

        Args:
            target_device_id: Device ID to connect to
            timeout_seconds: Connection timeout in seconds (default: CONNECTION_TIMEOUT)

        Returns:
            Device object if successful, None if timeout or failure

        Raises:
            RuntimeError: If connection times out or fails
        """
        if timeout_seconds is None:
            timeout_seconds = self.CONNECTION_TIMEOUT

        result = {"device": None, "error": None, "completed": False}

        def connection_worker():
            """Worker thread for connection attempt."""
            try:
                if BACKEND_TYPE == "seabreeze":
                    # For SeaBreeze, create Spectrometer directly from serial
                    logger.debug(f"SeaBreeze: Creating spectrometer for device {target_device_id}")
                    device = Spectrometer.from_serial_number(str(target_device_id))
                    result["device"] = device
                else:
                    # For OceanDirect API
                    logger.debug(f"OceanDirect: Opening device {target_device_id}")
                    device = self._api.open_device(target_device_id)
                    result["device"] = device
                result["completed"] = True
            except Exception as e:
                logger.error(f"Connection worker error: {e}")
                result["error"] = e
                result["completed"] = True

        # Start connection in separate thread
        connection_thread = threading.Thread(target=connection_worker, daemon=True)
        connection_thread.start()

        # Wait for completion or timeout
        connection_thread.join(timeout=timeout_seconds)

        if not result["completed"]:
            # Timeout occurred
            error_msg = f"Connection to {self.DEVICE_MODEL} device {target_device_id} timed out after {timeout_seconds}s"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        elif result["error"]:
            # Connection failed
            raise result["error"]
        elif result["device"] is None:
            # Unexpected case
            raise RuntimeError("Connection completed but no device returned")

        return result["device"]

    def discover_devices(self) -> list[int]:
        """Discover available USB4000 devices.

        Returns:
            List of device IDs for available USB4000 spectrometers

        Raises:
            RuntimeError: If device discovery fails

        """
        try:
            logger.debug("Scanning for Ocean Optics devices...")

            if BACKEND_TYPE == "seabreeze":
                # Use SeaBreeze device discovery
                devices = list_devices()
                logger.debug(f"SeaBreeze found {len(devices)} device(s)")

                # Extract device serial numbers as IDs
                self._device_ids = []
                for device in devices:
                    # SeaBreeze devices have serial numbers
                    serial = device.serial_number
                    self._device_ids.append(serial)
                    logger.debug(f"Found device: {device.model} (Serial: {serial})")

            else:
                # Use OceanDirect API discovery
                if self._api is None:
                    self._api = OceanDirectAPI()

                self._api.find_usb_devices()
                self._device_ids = self._api.get_device_ids()

            logger.info(
                f"Found {len(self._device_ids)} Ocean Optics device(s): {self._device_ids}",
            )
            return self._device_ids.copy()

        except Exception as e:
            error_msg = f"Device discovery failed: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def connect(self, device_id: Optional[int] = None) -> bool:
        """Connect to USB4000 device.

        Args:
            device_id: Specific device ID to connect to. If None, connects to first available.

        Returns:
            True if connection successful, False otherwise

        Raises:
            RuntimeError: If connection fails

        """
        if self._connected:
            logger.debug(f"{self.DEVICE_MODEL} already connected")
            return True

        try:
            # Discover devices if not already done
            if not self._device_ids:
                self.discover_devices()

            if not self._device_ids:
                raise RuntimeError("No Ocean Optics devices found")

            # Select target device
            if device_id is not None:
                if device_id not in self._device_ids:
                    logger.warning(
                        f"Device {device_id} not found, using {self._device_ids[0]}",
                    )
                    target_device_id = self._device_ids[0]
                else:
                    target_device_id = device_id
            else:
                target_device_id = self._device_ids[0]

            logger.info(f"Connecting to {self.DEVICE_MODEL} device {target_device_id}")

            # Open device connection with timeout protection
            logger.debug(f"Attempting connection with {self.CONNECTION_TIMEOUT}s timeout...")
            self._device = self._connection_with_timeout(target_device_id)
            self._connected = True

            # Initialize device properties
            self._initialize_device_properties()

            logger.info(
                f"Successfully connected to {self.DEVICE_MODEL} (device {target_device_id})",
            )
            return True

        except Exception as e:
            error_msg = f"Connection failed: {e}"
            logger.error(error_msg)
            self._connected = False
            raise RuntimeError(error_msg) from e

    def _initialize_device_properties(self):
        """Initialize device properties after connection."""
        try:
            # Get device information
            self._serial_number = getattr(self._device, "serial_number", "Unknown")

            # Get integration time limits - use constants if API methods not available
            try:
                self._min_integration_time = (
                    self._device.minimum_integration_time_micros / 1000000.0
                )  # Convert to seconds
            except AttributeError:
                logger.debug("Using fallback minimum integration time")
                self._min_integration_time = self.MIN_INTEGRATION_TIME

            try:
                self._max_integration_time = (
                    self._device.maximum_integration_time_micros / 1000000.0
                )  # Convert to seconds
            except AttributeError:
                logger.debug("Using fallback maximum integration time")
                self._max_integration_time = self.MAX_INTEGRATION_TIME

            # Get wavelength calibration
            try:
                self._wavelengths = np.array(self._device.wavelengths())
            except Exception as e:
                logger.warning(f"Failed to get wavelengths directly: {e}")
                # Use fallback wavelength calibration for USB4000
                self._wavelengths = self._get_fallback_wavelengths()

            # Set default integration time
            self.set_integration_time(self._current_integration_time)

            logger.debug("Device properties initialized:")
            logger.debug(f"  Serial: {self._serial_number}")
            logger.debug(
                f"  Integration time range: {self._min_integration_time:.3f}s - {self._max_integration_time:.1f}s",
            )
            logger.debug(
                f"  Wavelength range: {self._wavelengths[0]:.1f}nm - {self._wavelengths[-1]:.1f}nm",
            )
            logger.debug(f"  Pixel count: {len(self._wavelengths)}")

        except Exception as e:
            logger.warning(f"Failed to initialize some device properties: {e}")

    def disconnect(self):
        """Disconnect from USB4000 device."""
        if self._connected and self._device:
            try:
                # Close device connection if method exists
                if hasattr(self._device, 'close_device'):
                    self._device.close_device()
                elif hasattr(self._device, 'close'):
                    self._device.close()
                logger.info(f"Disconnected from {self.DEVICE_MODEL}")
            except Exception as e:
                logger.warning(f"Error during disconnect: {e}")

        self._device = None
        self._connected = False

    def _get_fallback_wavelengths(self) -> np.ndarray:
        """Generate fallback wavelength calibration for USB4000."""
        # USB4000 typical wavelength range: ~200-1100nm over 3648 pixels
        logger.debug("Using fallback wavelength calibration for USB4000")
        return np.linspace(200.0, 1100.0, 3648)

    def is_connected(self) -> bool:
        """Check if device is connected."""
        return self._connected and self._device is not None

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

        # Validate integration time
        if self._min_integration_time and self._max_integration_time:
            if (
                time_seconds < self._min_integration_time
                or time_seconds > self._max_integration_time
            ):
                logger.error(
                    f"Integration time {time_seconds:.3f}s out of range "
                    f"({self._min_integration_time:.3f}s - {self._max_integration_time:.1f}s)",
                )
                return False

        try:
            # SeaBreeze API uses microseconds
            time_microseconds = int(time_seconds * 1000000)
            self._device.integration_time_micros(time_microseconds)
            self._current_integration_time = time_seconds

            logger.debug(
                f"Set integration time to {time_seconds * 1000:.1f}ms ({time_microseconds}μs)",
            )
            return True

        except Exception as e:
            logger.error(f"Failed to set integration time: {e}")
            return False

    def get_integration_time(self) -> float:
        """Get current integration time in seconds."""
        return self._current_integration_time

    def acquire_spectrum(self) -> np.ndarray | None:
        """Acquire spectrum from USB4000.

        Returns:
            Spectrum intensity data as numpy array, or None if acquisition fails

        """
        if not self.is_connected():
            logger.error("Device not connected")
            return None

        try:
            # Acquire spectrum - different methods for different backends
            if BACKEND_TYPE == "seabreeze":
                # SeaBreeze uses intensities() method
                intensity_data = np.array(self._device.intensities())
            else:
                # OceanDirect uses get_formatted_spectrum() method
                intensity_data = np.array(self._device.get_formatted_spectrum())

            logger.debug(
                f"Acquired spectrum: {len(intensity_data)} points, "
                f"integration time: {self._current_integration_time:.3f}s",
            )

            return intensity_data

        except Exception as e:
            logger.error(f"Spectrum acquisition failed: {e}")
            return None

    def get_wavelengths(self) -> np.ndarray | None:
        """Get wavelength calibration data.

        Returns:
            Wavelength array in nanometers, or None if not available

        """
        if not self.is_connected():
            logger.error("Device not connected")
            return None

        return self._wavelengths.copy() if self._wavelengths is not None else None

    def get_device_info(self) -> dict[str, Any]:
        """Get device information.

        Returns:
            Dictionary containing device information

        """
        info = {
            "model": self.DEVICE_MODEL,
            "connected": self.is_connected(),
            "serial_number": self._serial_number,
            "integration_time": self._current_integration_time,
        }

        if self.is_connected():
            info.update(
                {
                    "min_integration_time": self._min_integration_time,
                    "max_integration_time": self._max_integration_time,
                    "pixel_count": len(self._wavelengths)
                    if self._wavelengths is not None
                    else None,
                    "wavelength_range": {
                        "min": float(self._wavelengths[0])
                        if self._wavelengths is not None
                        else None,
                        "max": float(self._wavelengths[-1])
                        if self._wavelengths is not None
                        else None,
                    }
                    if self._wavelengths is not None
                    else None,
                },
            )

        return info

    def close_device(self) -> bool:
        """Alias for disconnect() to match expected interface."""
        self.disconnect()
        return True

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()


def main():
    """Example usage of USB4000OceanDirect."""
    # Configure logging
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")

    if not OCEANDIRECT_AVAILABLE:
        print("❌ OceanDirect API not available")
        print("   Install with: pip install oceandirect")
        return

    try:
        # Create USB4000 interface
        usb4000 = USB4000OceanDirect()

        # Discover devices
        print("🔍 Discovering Ocean Optics devices...")
        devices = usb4000.discover_devices()
        print(f"📱 Found {len(devices)} device(s): {devices}")

        if not devices:
            print("❌ No devices found")
            return

        # Connect to device
        print("🔌 Connecting to USB4000...")
        if usb4000.connect():
            print("✅ Connected successfully")

            # Get device information
            info = usb4000.get_device_info()
            print("📋 Device Info:")
            for key, value in info.items():
                print(f"   {key}: {value}")

            # Set integration time
            print("⏱️  Setting integration time to 100ms...")
            usb4000.set_integration_time(0.1)

            # Acquire spectrum
            print("📊 Acquiring spectrum...")
            wavelengths = usb4000.get_wavelengths()
            intensity = usb4000.acquire_spectrum()

            if wavelengths is not None and intensity is not None:
                print(f"✅ Spectrum acquired: {len(intensity)} points")
                print(
                    f"   Wavelength range: {wavelengths[0]:.1f} - {wavelengths[-1]:.1f} nm",
                )
                print(
                    f"   Intensity range: {intensity.min():.1f} - {intensity.max():.1f}",
                )
            else:
                print("❌ Spectrum acquisition failed")

            # Disconnect
            usb4000.disconnect()
            print("🔌 Disconnected")

        else:
            print("❌ Connection failed")

    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()
