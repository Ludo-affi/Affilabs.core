"""USB4000 Spectrometer Driver - SINGLE CONNECTION METHOD ONLY

This is the ONLY way to connect to the USB4000/FLAME-T spectrometer.
Uses pyseabreeze backend (pure Python, requires WinUSB driver + libusb-1.0.dll).

Requirements:
- WinUSB driver installed via Zadig for the spectrometer device
- libusb-1.0.dll in C:\\Windows\\System32
- seabreeze Python package installed
"""

from utils.logger import logger

# SINGLE CONNECTION METHOD: pyseabreeze backend only
try:
    import seabreeze
    seabreeze.use('pyseabreeze')  # REQUIRED: Must use pyseabreeze, not cseabreeze
    from seabreeze.spectrometers import Spectrometer, list_devices
    SEABREEZE_AVAILABLE = True
    logger.info("USB4000: Using pyseabreeze backend (WinUSB + libusb)")
except ImportError as e:
    SEABREEZE_AVAILABLE = False
    logger.error(f"SeaBreeze not available: {e}")
    logger.error("Install with: pip install seabreeze")


class USB4000:
    """USB4000/FLAME-T Spectrometer using pyseabreeze backend.

    This is the ONLY connection method. No fallbacks, no alternatives.
    """

    def __init__(self, parent=None):
        """Initialize USB4000 driver."""
        self._device = None
        self.opened = False
        self.serial_number = None
        self.spec = None
        self.use_seabreeze = True  # Always True - single connection method
        self._wavelengths = None
        self._integration_time = 0.1

    def open(self):
        """Connect to spectrometer - SINGLE METHOD ONLY."""
        try:
            logger.info("Connecting to USB4000...")

            if not SEABREEZE_AVAILABLE:
                logger.error("SeaBreeze not available")
                return False

            # Discover devices (NEW software method)
            logger.debug("Scanning for Ocean Optics devices...")
            devices = list_devices()
            logger.debug(f"SeaBreeze found {len(devices)} device(s)")

            if not devices:
                logger.warning("No USB4000 devices found")
                return False

            # Get first device serial number
            device_info = devices[0]
            target_serial = device_info.serial_number
            logger.info(f"Connecting to device serial: {target_serial}")

            # Connect using SeaBreeze (NEW software method)
            logger.debug(f"SeaBreeze: Creating spectrometer for serial {target_serial}")
            self._device = Spectrometer.from_serial_number(target_serial)

            # Set connection state
            self.opened = True
            self.serial_number = target_serial
            self.spec = self._device

            # Initialize wavelengths
            try:
                self._wavelengths = self._device.wavelengths()
                logger.debug(f"Wavelength range: {self._wavelengths[0]:.1f} - {self._wavelengths[-1]:.1f} nm")
            except Exception as e:
                logger.warning(f"Could not read wavelengths: {e}")

            # Log detector capabilities
            try:
                min_int_us = self._device.minimum_integration_time_micros
                min_max_limits = self._device.integration_time_micros_limits
                max_intensity = getattr(self._device, "max_intensity", None)
                logger.info(
                    f"Detector integration time limits: {min_max_limits[0]}µs - {min_max_limits[1]}µs "
                    f"({min_max_limits[0]/1000:.2f}ms - {min_max_limits[1]/1000:.2f}ms)"
                )
                if max_intensity is not None:
                    logger.info(f"Detector max_intensity (a.u.): {max_intensity}")
            except Exception as e:
                logger.warning(f"Could not read detector capabilities: {e}")

            logger.info(f"USB4000 connected: {self.serial_number}")
            return True

        except Exception as e:
            logger.error(f"USB4000 connection failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def close(self):
        """Close connection."""
        try:
            if self._device:
                self._device.close()
            self.opened = False
        except Exception as e:
            logger.warning(f"Error closing: {e}")

    def set_integration(self, time_ms):
        """Set integration time.

        Args:
            time_ms: Integration time in milliseconds (matches settings.py)
        """
        if not self._device or not self.opened:
            return False
        try:
            # Convert milliseconds to microseconds for SeaBreeze API
            time_us = int(time_ms * 1000)

            # Set the integration time (this is a setter only, returns None)
            self._device.integration_time_micros(time_us)

            # Store in seconds for internal use
            self._integration_time = time_ms / 1000.0

            logger.debug(f"Set integration time: {time_ms:.2f}ms ({time_us}µs)")
            return True
        except Exception as e:
            logger.error(f"set_integration error: {e}")
            return False

    def read_intensity(self):
        """Read intensities."""
        if not self._device or not self.opened:
            return None
        try:
            import numpy as np
            return np.array(self._device.intensities())
        except Exception as e:
            logger.error(f"read_intensity error: {e}")
            return None

    @property
    def wavelengths(self):
        """Get wavelengths."""
        if self._wavelengths is not None:
            return self._wavelengths
        if self._device:
            try:
                self._wavelengths = self._device.wavelengths()
                return self._wavelengths
            except Exception as e:
                logger.debug(f"Could not read wavelengths: {e}")
        return None

    @property
    def min_integration(self):
        """Get min integration time."""
        if self._device:
            try:
                # SeaBreeze returns in microseconds, convert to seconds
                return self._device.minimum_integration_time_micros / 1_000_000
            except Exception as e:
                logger.debug(f"Could not read min integration time: {e}")
        return 0.001

    def read_wavelength(self):
        """Get wavelengths array."""
        return self.wavelengths
